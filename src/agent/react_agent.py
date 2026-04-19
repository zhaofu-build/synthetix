"""
ReAct Agent 模块

基于 TAOR（Think→Act→Observe→Repeat）循环的智能对话代理。
"笨引擎 + 聪明模型"：运行时不含业务逻辑，所有智能决策由 LLM 完成。
"""
import json
import re
import logging
from typing import Dict, List, Optional, Any

from src.agent.tool_registry import registry
from src.agent.session_manager import DialogState, SessionStatus, get_session_manager
from src.application.services.llm_adapter import generate_response_async, select_model

logger = logging.getLogger(__name__)

# ==================== 系统提示词 ====================

END_CALL = "<" + "/tool_call>"  # 避免被当成 XML 或 format 占位符


def build_system_prompt(tools_description: str, project_id, project_name: str) -> str:
    """构建系统提示词，纯字符串拼接"""
    pid = project_id or "无"
    pname = project_name or "无"
    parts = [
        "你是一个 AI 视频剪辑助手。你可以使用以下工具来帮助用户。",
        "",
        "## 可用工具",
        "",
        tools_description,
        "",
        "## 工具调用格式",
        "",
        "当你需要调用工具时，必须使用以下格式：",
        "",
        '<tool_call name="工具名">',
        "参数JSON",
        END_CALL,
        "",
        "例如：",
        '<tool_call name="list_videos">',
        '{"project_id": ' + str(project_id or 0) + '}',
        END_CALL,
        "",
        '<tool_call name="get_video_description">',
        '{"video_id": 3}',
        END_CALL,
        "",
        "## 规则",
        "",
        "1. 可以在同一条回复中调用多个工具，也可以不调用任何工具直接回复",
        "2. 工具调用后你会收到 <tool_result> 结果，然后继续回复",
        "3. 回复用中文，简洁自然",
        '4. 如果用户问"第X个"视频/素材，先调用 list_videos 获取列表，再根据序号找到对应 ID 调用其他工具',
        "5. 如果素材没有描述，主动询问用户是否需要 AI 分析",
        "6. 对于只读查询（查看、搜索、分析），直接执行不需要确认",
        "7. 对于会修改/删除/渲染的操作，先向用户确认再调用工具",
        "",
        "## 当前上下文",
        "",
        "- 项目 ID: " + str(pid),
        "- 项目名: " + str(pname),
        "",
    ]
    return "\n".join(parts)


class ReActAgent:
    """基于 TAOR 循环的对话代理"""

    MAX_ITERATIONS = 5  # 最大循环次数，防止无限循环

    def __init__(self):
        self.sessions = get_session_manager()

    async def process_message(
        self,
        session_id: Optional[str],
        user_input: str,
        context: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        处理用户消息 - TAOR 循环入口

        Args:
            session_id: 会话 ID
            user_input: 用户输入
            context: 上下文（含 project_id）

        Returns:
            响应结果
        """
        # 获取或创建会话
        state = self.sessions.get_or_create_session(session_id)
        state.add_message("user", user_input)

        # 合并上下文
        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)

        logger.info(f"[ReAct] 用户输入: '{user_input}', project_id={state.project_id}")

        try:
            # TAOR 循环
            final_reply = await self._taor_loop(state, user_input)

            state.add_message("assistant", final_reply)
            self.sessions.persist_session(state)

            return {
                "reply": final_reply,
                "status": "completed",
                "session_id": state.session_id,
            }

        except Exception as e:
            logger.error(f"[ReAct] 处理失败: {e}", exc_info=True)
            return {
                "reply": f"处理时出现错误: {str(e)}",
                "status": "error",
                "session_id": state.session_id,
            }

    async def process_message_stream(
        self,
        session_id: Optional[str],
        user_input: str,
        context: Optional[Dict] = None,
    ):
        """
        流式处理用户消息，逐步 yield SSE 事件字典。

        事件类型:
        - session: 会话信息
        - thinking: AI 思考中
        - tool_start: 工具开始执行
        - tool_result: 工具执行结果
        - reply: 最终回复（可能多次追加）
        - done: 处理完成
        - error: 处理出错
        """
        state = self.sessions.get_or_create_session(session_id)
        state.add_message("user", user_input)

        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)

        yield {"type": "session", "session_id": state.session_id}
        logger.info(f"[ReAct-Stream] 用户输入: '{user_input}', project_id={state.project_id}")

        try:
            messages = self._build_messages(state)
            final_reply = ""

            for iteration in range(self.MAX_ITERATIONS):
                yield {"type": "thinking", "iteration": iteration + 1}

                model = select_model(messages, iteration=iteration)
                response_text = await generate_response_async(
                    messages=messages,
                    model_name=model,
                    temperature=0.7,
                    max_tokens=2048,
                )

                tool_calls = self._parse_tool_calls(response_text)

                if not tool_calls:
                    final_reply = self._strip_tool_call_hints(response_text)
                    yield {"type": "reply", "content": final_reply}
                    break

                # 逐个执行工具并推送状态
                tool_results = []
                for tc in tool_calls:
                    tool_name = tc["name"]
                    tool_params = tc["params"]

                    # 检查工具权限
                    tool = registry.get_tool(tool_name)
                    perm = tool.permission if tool else "modify"

                    yield {
                        "type": "tool_start",
                        "tool": tool_name,
                        "params": tool_params,
                        "permission": perm,
                    }

                    result = await self._execute_tool(tool_name, tool_params, state)
                    tool_results.append({
                        "name": tool_name,
                        "params": tool_params,
                        "result": result,
                    })

                    if tool_name == "list_videos" and result.get("videos"):
                        state.last_video_list = result["videos"]

                    # 截断结果用于推送
                    result_preview = json.dumps(result, ensure_ascii=False, default=str)
                    if len(result_preview) > 500:
                        result_preview = result_preview[:500] + "...(已截断)"

                    yield {
                        "type": "tool_result",
                        "tool": tool_name,
                        "success": result.get("success", True),
                        "preview": result_preview,
                    }

                # Observe
                messages.append({"role": "assistant", "content": response_text})
                observation = self._format_observations(tool_results)
                messages.append({"role": "user", "content": observation})
            else:
                # 超过最大循环次数
                final_reply = response_text if response_text else "处理超时，请简化您的问题后重试。"
                yield {"type": "reply", "content": final_reply}

            state.add_message("assistant", final_reply)
            self.sessions.persist_session(state)
            yield {"type": "done", "status": "completed", "session_id": state.session_id}

        except Exception as e:
            logger.error(f"[ReAct-Stream] 处理失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e), "session_id": state.session_id}

    async def _taor_loop(self, state: DialogState, user_input: str) -> str:
        """
        TAOR 主循环: Think → Act → Observe → Repeat

        每轮将历史消息 + 工具结果发送给 LLM，
        LLM 要么直接回复用户，要么输出 <tool_call/> 调用工具。
        如果有工具调用，执行后把结果加入消息历史，继续下一轮。
        """
        # 构建消息历史（最近 20 条）
        messages = self._build_messages(state)

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(f"[ReAct] 第{iteration+1}轮循环")

            # Think: 调用 LLM（快慢双脑路由）
            model = select_model(messages, iteration=iteration)
            response_text = await generate_response_async(
                messages=messages,
                model_name=model,
                temperature=0.7,
                max_tokens=2048,
            )
            logger.info(f"[ReAct] LLM响应 (前200字): {response_text[:200]}")

            # 解析工具调用
            tool_calls = self._parse_tool_calls(response_text)

            if not tool_calls:
                # 无工具调用 → 循环结束，直接回复用户
                clean_reply = self._strip_tool_call_hints(response_text)
                return clean_reply

            # Act: 执行工具调用
            tool_results = []
            for tc in tool_calls:
                result = await self._execute_tool(tc["name"], tc["params"], state)
                tool_results.append({
                    "name": tc["name"],
                    "params": tc["params"],
                    "result": result,
                })
                logger.info(f"[ReAct] 工具 {tc['name']} 执行完成, success={result.get('success', True)}")

                # 缓存视频列表供序数解析
                if tc["name"] == "list_videos" and result.get("videos"):
                    state.last_video_list = result["videos"]

            # Observe: 将 LLM 回复 + 工具结果加入消息历史
            messages.append({"role": "assistant", "content": response_text})
            observation = self._format_observations(tool_results)
            messages.append({"role": "user", "content": observation})
            logger.info(f"[ReAct] 观察: {observation[:300]}")

        # 超过最大循环次数
        return response_text if response_text else "处理超时，请简化您的问题后重试。"

    def _build_messages(self, state: DialogState) -> List[Dict[str, str]]:
        """构建发送给 LLM 的消息列表"""
        # 系统提示词
        tools_desc = registry.get_tools_description()
        project_name = ""
        if state.project_id:
            try:
                from src.infrastructure.db.session import get_db_context
                from src.domain.entities.video_project import VideoProject
                with get_db_context() as db:
                    proj = db.query(VideoProject).filter(VideoProject.id == state.project_id).first()
                    if proj:
                        project_name = proj.name
            except Exception:
                pass

        system_prompt = build_system_prompt(tools_desc, state.project_id, project_name)

        messages = [{"role": "system", "content": system_prompt}]

        # 历史消息（最近 20 条）
        history = state.history[-20:] if state.history else []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        return messages

    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        解析 LLM 响应中的工具调用

        格式: <tool_call name="tool_name">\n{"key": "value"}\n</tool_call}>
        """
        calls = []
        pattern = r'<tool_call\s+name=["\']([^"\']+)["\']>\s*\n?(.*?)\n?\s*</tool_call\s*>?'
        matches = re.findall(pattern, text, re.DOTALL)

        for name, params_str in matches:
            try:
                params = json.loads(params_str.strip())
            except (json.JSONDecodeError, ValueError):
                params = {}
            calls.append({"name": name.strip(), "params": params})

        return calls

    async def _execute_tool(
        self, tool_name: str, params: Dict, state: DialogState
    ) -> Dict[str, Any]:
        """执行单个工具"""
        tool = registry.get_tool(tool_name)
        if not tool:
            return {"success": False, "error": f"未知工具: {tool_name}"}

        # 注入 project_id
        if state.project_id and "project_id" not in params:
            params["project_id"] = state.project_id

        try:
            # 参数校验
            validated = tool.validate_params(params) if tool.param_model else params

            # before_execute hook
            if tool.before_execute:
                validated = tool.before_execute(validated) or validated

            # 执行
            result = await tool.execute(**validated)

            # after_execute hook
            if tool.after_execute:
                result = tool.after_execute(result) or result

            return result

        except Exception as e:
            logger.error(f"[ReAct] 工具 {tool_name} 执行异常: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _format_observations(self, tool_results: List[Dict]) -> str:
        """将工具执行结果格式化为观察消息"""
        parts = ["以下是工具执行结果：\n"]
        for tr in tool_results:
            result = tr["result"]
            # 截断过长的结果
            result_str = json.dumps(result, ensure_ascii=False, default=str)
            if len(result_str) > 3000:
                result_str = result_str[:3000] + "...(已截断)"
            parts.append(
                f'<tool_result name="{tr["name"]}">\n{result_str}\n</tool_result>'
            )
        parts.append("\n请根据以上工具结果，用自然语言回复用户。如果还需要调用其他工具，继续使用 <tool_call/> 格式。")
        return "\n".join(parts)

    def _strip_tool_call_hints(self, text: str) -> str:
        """去除回复中的工具调用标记和深度思考块，只保留自然语言部分"""
        # 移除 <tool_call...>...</tool_call} 块
        clean = re.sub(
            r'<tool_call\s+name=["\'][^"\']*["\']>\s*\n?.*?\n?\s*</tool_call\s*>?',
            '', text, flags=re.DOTALL
        )
        # 移除深度思考块 <think ...>...</think} 或 <thinking>...</thinking}
        clean = re.sub(r'<think(?:ing)?>.*?</think(?:ing)?>', '', clean, flags=re.DOTALL)
        return clean.strip()


# ==================== 全局单例 ====================

_react_agent: Optional[ReActAgent] = None


def get_react_agent() -> ReActAgent:
    """获取全局 ReAct Agent 实例"""
    global _react_agent
    if _react_agent is None:
        _react_agent = ReActAgent()
    return _react_agent
