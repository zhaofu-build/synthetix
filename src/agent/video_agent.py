"""
视频对话代理主模块

实现对话式视频剪辑的核心逻辑
"""
import json
import logging
from typing import Dict, List, Optional, Any

from src.agent.session_manager import SessionManager, SessionStatus, DialogState, get_session_manager
from src.agent.intent_recognizer import IntentRecognizer, get_intent_recognizer
from src.agent.slot_filler import SlotFiller, get_slot_filler
from src.agent.tool_registry import registry
from src.agent.prompts import AgentPrompts as Prompts
from src.infrastructure.db.session import get_db_context
from src.infrastructure.repositories import VideoRepository

logger = logging.getLogger(__name__)


class VideoDialogAgent:
    """视频对话代理"""

    def __init__(
        self,
        session_manager: SessionManager = None,
        intent_recognizer: IntentRecognizer = None,
        slot_filler: SlotFiller = None
    ):
        """
        初始化代理

        Args:
            session_manager: 会话管理器
            intent_recognizer: 意图识别器
            slot_filler: 槽位填充器
        """
        self.sessions = session_manager or get_session_manager()
        self.intents = intent_recognizer or get_intent_recognizer()
        self.slots = slot_filler or get_slot_filler()
        self.prompts = Prompts()

    async def process_message(
        self,
        session_id: Optional[str],
        user_input: str,
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        处理用户消息

        Args:
            session_id: 会话 ID（可选）
            user_input: 用户输入
            context: 上下文信息

        Returns:
            Dict: 响应结果
        """
        # 获取或创建会话
        state = self.sessions.get_or_create_session(session_id)

        # 添加用户消息到历史
        state.add_message("user", user_input)

        # 合并上下文
        if context:
            if "current_video_id" in context:
                state.current_video_id = context["current_video_id"]
        # 从请求中提取 project_id（API 层传入）
        request_pid = context.get("project_id") if context else None
        if request_pid:
            state.project_id = int(request_pid)

        try:
            # 根据当前状态处理
            if state.status == SessionStatus.IDLE:
                result = await self._handle_idle(state, user_input)

            elif state.status == SessionStatus.COLLECTING:
                result = await self._handle_collecting(state, user_input)

            elif state.status == SessionStatus.CONFIRMING:
                result = await self._handle_confirming(state, user_input)

            elif state.status == SessionStatus.EXECUTING:
                result = {
                    "reply": "正在执行中，请稍候...",
                    "status": "executing"
                }

            else:
                result = await self._handle_idle(state, user_input)

        except Exception as e:
            logger.error(f"处理消息失败: {e}", exc_info=True)
            state.status = SessionStatus.ERROR
            result = {
                "reply": f"处理时出现错误: {str(e)}",
                "status": "error"
            }

        # 添加助手消息到历史
        state.add_message("assistant", result.get("reply", ""))

        # 持久化会话状态到数据库
        self.sessions.persist_session(state)

        # 构建返回结果
        result["session_id"] = state.session_id
        return result

    async def _handle_idle(self, state, user_input: str) -> Dict[str, Any]:
        """处理空闲状态"""
        logger.info(f"[IDLE] 用户输入: '{user_input}', project_id={state.project_id}")

        # 获取当前视频信息
        current_video = await self._get_current_video_name(state)

        # 意图识别
        intent_result = await self.intents.recognize(
            user_input=user_input,
            history=state.history,
            current_video=current_video
        )

        logger.info(f"[意图识别] 结果={intent_result.intent}, 置信度={intent_result.confidence}, "
                     f"need_clarification={intent_result.need_clarification}")

        # 处理确认/取消（可能在确认后重新开始）
        if intent_result.intent == "confirm":
            return {
                "reply": "当前没有待执行的操作。请告诉我您想做什么？",
                "status": "idle"
            }

        if intent_result.intent == "cancel":
            state.reset()
            return {
                "reply": "操作已取消。请告诉我您想做什么？",
                "status": "idle"
            }

        # 帮助
        if intent_result.intent == "help":
            return {
                "reply": self.prompts.HELP_RESPONSE,
                "status": "idle"
            }

        # 需要澄清
        if intent_result.need_clarification:
            return {
                "reply": intent_result.clarification_question,
                "status": "idle"
            }

        # 未知意图
        if intent_result.intent == "unknown":
            return {
                "reply": "抱歉，我没理解您的意思。您可以尝试说：\n"
                        "- 帮我剪辑视频的前30秒\n"
                        "- 帮我做一个30秒的混剪\n"
                        "- 查看我的素材库",
                "status": "idle"
            }

        # 设置意图和状态
        state.intent = intent_result.intent
        state.slots = intent_result.entities.copy()
        state.status = SessionStatus.COLLECTING

        # 继续收集信息
        return await self._handle_collecting(state, user_input)

    async def _handle_collecting(self, state, user_input: str) -> Dict[str, Any]:
        """处理信息收集状态"""
        # 获取意图需要的槽位
        intent_info = self.intents.get_intent_info(state.intent)
        required_slots = intent_info.get("required_slots", [])
        all_slots = intent_info.get("slots", [])

        logger.info(f"[收集] 意图={state.intent}, 需要槽位={required_slots}, "
                     f"已有槽位={list(state.slots.keys())}, last_video_list={len(state.last_video_list)}个, "
                     f"project_id={state.project_id}")

        # ★ 序数解析优先：在 slot filler 之前解析"第一个/第二个"
        # 避免 LLM 生成错误的 video_id 占位符
        if "video_id" in all_slots and "video_id" not in state.slots:
            # last_video_list 为空但有 project_id → 自动加载项目素材
            if not state.last_video_list and state.project_id:
                await self._load_project_videos(state)

            if state.last_video_list:
                ordinal = self._extract_ordinal(user_input)
                logger.info(f"[序数解析] 输入='{user_input}', 序数={ordinal}, 视频列表={[v.get('id') for v in state.last_video_list]}")
                if ordinal is not None and 0 <= ordinal < len(state.last_video_list):
                    state.slots["video_id"] = state.last_video_list[ordinal]["id"]
                    logger.info(f"[序数解析] 命中: 第{ordinal+1}个 → video_id={state.slots['video_id']}")

        # 从用户输入中提取槽位（video_id 已填充时会被跳过）
        new_slots = await self.slots.fill(
            user_input=user_input,
            slot_names=all_slots,
            filled_slots=state.slots
        )
        if new_slots:
            logger.info(f"[槽位提取] 新提取: {new_slots}")
        state.slots.update(new_slots)

        # 特殊处理：如果当前有视频但没指定，自动填充
        if "video_id" in required_slots and "video_id" not in state.slots:
            if state.current_video_id:
                state.slots["video_id"] = state.current_video_id
                logger.info(f"[自动填充] 使用 current_video_id={state.current_video_id}")
            elif state.last_referenced_video_id:
                state.slots["video_id"] = state.last_referenced_video_id
                logger.info(f"[自动填充] 使用 last_referenced_video_id={state.last_referenced_video_id}")

        # 记录最后引用的视频 ID（供后续"帮我分析"使用）
        if "video_id" in state.slots and state.slots["video_id"]:
            state.last_referenced_video_id = state.slots["video_id"]

        # 检查缺失的必填槽位
        missing = self.slots.get_missing_slots(required_slots, state.slots)

        if missing:
            # 还有缺失的槽位，继续询问
            logger.info(f"[收集] 缺失槽位: {[s.name for s in missing]}, 当前slots={state.slots}")
            return {
                "reply": missing[0].prompt,
                "status": "collecting",
                "missing_slots": [s.name for s in missing]
            }

        # 所有必填槽位已填充，构建待执行操作
        action = await self._build_action(state)
        state.pending_action = action
        logger.info(f"[收集完成] 工具={action.get('tool')}, 参数={action.get('params')}")

        # 只读查询工具：跳过确认，直接执行
        if self._is_readonly_tool(action.get("tool", "")):
            logger.info(f"[直接执行] 只读工具 {action.get('tool')}，跳过确认")
            state.status = SessionStatus.EXECUTING
            # 注入 project_id 到参数中
            if state.project_id:
                action["params"]["project_id"] = state.project_id
            result = await self._execute_action(action)
            state.status = SessionStatus.IDLE
            # 缓存视频列表供后续引用（如"第一个"）
            if action.get("tool") == "list_videos" and result.get("videos"):
                state.last_video_list = result["videos"]
                logger.info(f"[缓存] 视频列表已缓存，共{len(result['videos'])}个")

            reply = result.get("message", "查询完成")
            if result.get("success") is False:
                reply = f"操作失败：{result.get('error', '未知错误')}"
            logger.info(f"[执行结果] success={result.get('success')}, reply长度={len(reply)}")

            return {
                "reply": reply,
                "status": "completed",
                "result": result,
                "action": action,
            }

        # 生成确认消息
        confirmation = self._format_confirmation(action)

        return {
            "reply": confirmation,
            "status": "confirming",
            "action": action
        }

    async def _handle_confirming(self, state, user_input: str) -> Dict[str, Any]:
        """处理确认状态"""
        # 快速匹配确认/取消
        text = user_input.lower().strip()

        if text in ["确认", "好的", "可以", "是", "执行", "确定", "ok", "yes"]:
            # 执行操作
            state.status = SessionStatus.EXECUTING
            result = await self._execute_action(state.pending_action)

            # 缓存视频列表供后续引用
            tool_executed = state.pending_action.get("tool", "") if state.pending_action else ""
            if tool_executed == "list_videos" and result.get("videos"):
                state.last_video_list = result["videos"]

            if result.get("success"):
                state.status = SessionStatus.COMPLETED
                reply = f"✅ {result.get('message', '操作完成')}"

                # 如果有输出文件，提供预览
                if "output_path" in result:
                    reply += f"\n\n输出文件：{result['output_path']}"
            else:
                state.status = SessionStatus.ERROR
                reply = f"❌ 执行失败：{result.get('error', '未知错误')}"

            # 记录工具名（reset 前保存）
            tool_name = state.pending_action.get("tool", "") if state.pending_action else ""

            # 重置状态，准备下一个任务
            state.reset()

            result["tool"] = tool_name

            return {
                "reply": reply,
                "status": "completed" if result.get("success") else "error",
                "result": result
            }

        if text in ["取消", "不要", "不行", "否", "算了", "cancel", "no"]:
            state.reset()
            return {
                "reply": "操作已取消。请告诉我您想做什么？",
                "status": "idle"
            }

        # 用户可能想修改
        state.status = SessionStatus.COLLECTING
        return await self._handle_collecting(state, user_input)

    async def _build_action(self, state) -> Dict[str, Any]:
        """构建待执行操作"""
        return {
            "tool": state.intent,
            "params": state.slots.copy()
        }

    # 只读工具列表，无需确认直接执行
    READONLY_TOOLS = {
        "list_videos", "list_audios", "search_material", "search_files",
        "get_current_time", "get_system_info", "list_directory",
        "get_video_detail", "get_video_description", "analyze_video", "analyze_video_vl",
        "transcribe_video", "task_status", "help",
        "detect_language", "time_convert", "scene_detect", "extract_frames",
    }

    def _is_readonly_tool(self, tool_name: str) -> bool:
        """判断是否为只读查询工具"""
        return tool_name in self.READONLY_TOOLS

    async def _load_project_videos(self, state) -> None:
        """从项目加载素材列表到 last_video_list"""
        if not state.project_id:
            return
        try:
            from src.domain.entities.video_project import VideoProject
            with get_db_context() as db:
                project = db.query(VideoProject).filter(VideoProject.id == state.project_id).first()
                if project and project.material_ids:
                    videos = db.query(VideoRepository._model).filter(
                        VideoRepository._model.id.in_(project.material_ids)
                    ).all() if hasattr(VideoRepository, '_model') else []
                    # 直接用 VideoRepository 查询
                    repo = VideoRepository(db)
                    video_list = []
                    for mid in project.material_ids:
                        v = repo.get_by_id(mid)
                        if v:
                            video_list.append({
                                "id": v.id,
                                "name": v.video_name,
                                "duration": v.duration_hms,
                            })
                    state.last_video_list = video_list
                    logger.info(f"[项目素材加载] project_id={state.project_id}, 加载{len(video_list)}个素材")
        except Exception as e:
            logger.warning(f"[项目素材加载] 失败: {e}")

    @staticmethod
    def _extract_ordinal(text: str) -> Optional[int]:
        """从文本中提取序数（第几个），返回 0-based 索引"""
        import re
        cn_nums = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4,
                   "六": 5, "七": 6, "八": 7, "九": 8, "十": 9}
        # 匹配 "第一个" "第二个" "第1个"
        m = re.search(r"第([一二三四五六七八九十\d]+)[个号个]", text)
        if m:
            val = m.group(1)
            if val.isdigit():
                return int(val) - 1
            if val in cn_nums:
                return cn_nums[val]
        # 匹配 "第一个素材" "第2个视频"
        m = re.search(r"第([一二三四五六七八九十\d]+)", text)
        if m:
            val = m.group(1)
            if val.isdigit():
                return int(val) - 1
            if val in cn_nums:
                return cn_nums[val]
        return None

    def _format_confirmation(self, action: Dict) -> str:
        """格式化确认消息"""
        tool = action.get("tool", "")
        params = action.get("params", {})

        # 工具名称映射
        tool_names = {
            "cut_video": "剪切视频",
            "merge_videos": "合并视频",
            "add_subtitle": "添加字幕",
            "add_audio": "添加音频",
            "change_speed": "调整速度",
            "smart_clip": "智能剪辑",
            "analyze_video": "分析视频",
            "generate_tts": "生成语音",
            "list_videos": "查看素材",
            "search_material": "搜索素材"
        }

        lines = [f"请确认以下操作：", f"**操作：{tool_names.get(tool, tool)}**"]

        # 参数格式化
        param_names = {
            "video_id": "视频",
            "start_time": "开始时间",
            "end_time": "结束时间",
            "duration": "时长",
            "speed_factor": "速度倍数",
            "description": "描述",
            "keywords": "关键词"
        }

        for key, value in params.items():
            if value is not None:
                name = param_names.get(key, key)
                lines.append(f"- {name}: {value}")

        lines.append("\n回复 **确认** 执行，或告诉我需要修改的内容。")

        return "\n".join(lines)

    async def _execute_action(self, action: Dict) -> Dict[str, Any]:
        """执行操作（带循环纠错重试 + Hook 机制）"""
        from src.shared.constants import AgentConfig

        tool_name = action.get("tool")
        params = action.get("params", {})

        tool = registry.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"未知工具: {tool_name}"
            }

        # 参数校验（如果工具定义了 Pydantic 模型）
        try:
            validated_params = tool.validate_params(params)
        except Exception as e:
            return {"success": False, "error": f"参数校验失败: {e}"}

        # BEFORE hook
        if tool.before_execute:
            try:
                hook_result = tool.before_execute(validated_params)
                if hook_result is not None:
                    validated_params = hook_result
            except Exception as e:
                logger.warning(f"工具 {tool_name} before_execute hook 失败: {e}")
                return {"success": False, "error": str(e)}

        last_error = None
        current_params = validated_params.copy()

        for attempt in range(AgentConfig.MAX_ACTION_RETRIES + 1):
            try:
                result = await tool.execute(**current_params)
                if result.get("success", True):
                    # AFTER hook
                    if tool.after_execute:
                        try:
                            hook_result = tool.after_execute(result)
                            if hook_result is not None:
                                result = hook_result
                        except Exception as e:
                            logger.warning(f"工具 {tool_name} after_execute hook 失败: {e}")
                    return result

                # 工具返回了业务失败
                last_error = result.get("error", "未知错误")
                logger.warning(f"工具 {tool_name} 第 {attempt + 1} 次执行失败: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"执行工具 {tool_name} 第 {attempt + 1} 次异常: {e}", exc_info=True)

            # 如果还有重试机会，让 LLM 修正参数
            if attempt < AgentConfig.MAX_ACTION_RETRIES:
                corrected = await self._correct_params_with_llm(
                    tool_name, current_params, last_error
                )
                if corrected:
                    # 重新校验 LLM 修正的参数
                    try:
                        current_params = tool.validate_params(corrected)
                    except Exception:
                        logger.warning("LLM 修正的参数校验失败，放弃重试")
                        break
                    logger.info(f"LLM 修正参数后重试: {current_params}")
                else:
                    break  # LLM 无法修正，直接退出

        return {"success": False, "error": last_error}

    async def _correct_params_with_llm(
        self,
        tool_name: str,
        params: Dict,
        error_msg: str
    ) -> Optional[Dict]:
        """使用 LLM 根据错误信息修正参数"""
        from src.application.services.llm_adapter import generate_response
        from src.shared.utils.string_util import safe_parse_llm_json

        prompt = f"""工具执行失败，请根据错误信息修正参数。

工具名称: {tool_name}
原始参数: {json.dumps(params, ensure_ascii=False)}
错误信息: {error_msg}

请返回修正后的参数 JSON（不要包含 ```json 标记），只返回参数字典。
如果无法修正，返回 null。"""

        try:
            messages = [{"role": "user", "content": prompt}]
            response = generate_response(messages)
            result = safe_parse_llm_json(response)
            if result is None:
                return None
            return result if isinstance(result, dict) else None
        except Exception as e:
            logger.warning(f"LLM 参数修正失败: {e}")
            return None

    async def _get_current_video_name(self, state) -> str:
        """获取当前视频名称"""
        if not state.current_video_id:
            return "无"

        try:
            with get_db_context() as db:
                repo = VideoRepository(db)
                video = repo.get_by_id(state.current_video_id)
                return video.video_name if video else "无"
        except:
            return "无"


# 全局 Agent 实例
_agent: Optional[VideoDialogAgent] = None


def get_video_agent() -> VideoDialogAgent:
    """获取全局 Agent 实例"""
    global _agent
    if _agent is None:
        _agent = VideoDialogAgent()
    return _agent
