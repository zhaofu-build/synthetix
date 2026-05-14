"""
ReAct Agent 模块

基于 TAOR（Think→Act→Observe→Repeat）循环的智能对话代理。
"笨引擎 + 聪明模型"：运行时不含业务逻辑，所有智能决策由 LLM 完成。
"""
import json
import os
import re
import logging
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

from src.agent.tool_registry import registry
from src.agent.session_manager import DialogState, SessionStatus, get_session_manager
from src.agent.project_memory import get_project_memory, extract_preferences_from_messages
from src.application.services.llm_adapter import generate_response_async, select_model
from src.shared.utils.core_nexus_client import get_client

logger = logging.getLogger(__name__)

# ==================== 超时配置 ====================
LLM_TIMEOUT = 180  # LLM 调用超时 3 分钟
LLM_MAX_RETRIES = 2  # LLM 调用重试次数
LLM_RETRY_DELAY = 2  # 重试间隔（秒）

# ==================== 工具调用解析 ====================
TOOL_CALL_PATTERN = r'<tool_call\s+name=["\']([^"\']+)["\']>\s*\n?(.*?)\n?\s*</tool_call\s*>?'
END_CALL = "<" + "/tool_call>"
TOOL_TIMEOUTS = {
    "default": 120,
    "download_video": 300,
    "search_material": 300,
    "stabilize_video": 600,
    "smart_clip": 300,
    "scene_detect": 300,
    "batch_compress": 600,
    "analyze_video_vl": 180,
    "transcribe_video": 180,
    "generate_music": 300,
}

# ==================== 快速通道规则 ====================
# 简单指令直接匹配正则 → 调用工具 → 跳过 LLM TAOR 循环

_FAST_PATH_RULES: List[Tuple[str, str, Dict]] = [
    # (regex, tool_name, param_extractors: {param: group_index_or_const})
    (r"^(?:把|将|请)?(?:第?(\d+)[个号]?)?\s*视频?\s*(?:从|在)?(.+?)(?:到|至|-)(.+?)\s*(?:剪切|剪出来|裁剪|截取|剪出|切出)",
     "cut_video", {"video_index": 1, "start_time": 2, "end_time": 3}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*合并",
     "merge_videos", {}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*(?:旋转|转)\s*(\d+)\s*度",
     "rotate_video", {"video_index": 1, "angle": 2}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*压缩",
     "compress_video", {"video_index": 1}),
    (r"^(?:从|把)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*提取音频",
     "extract_audio", {"video_index": 1}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*转\s*GIF",
     "convert_to_gif", {"video_index": 1}),
    (r"^(?:查看|列出|显示|看看|有什么|所有|全部)\s*(?:素材|视频|材料|视频列表)",
     "list_videos", {}),
    (r"^(?:第?(\d+)[个号]?)?\s*视频?\s*(?:的)?(?:信息|详情|描述|元数据)",
     "get_video_description", {"video_index": 1}),
    (r"^提取\s*(?:第?(\d+)[个号]?)?\s*视频?\s*(?:的)?(?:关键帧|帧)",
     "extract_keyframes", {"video_index": 1}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*(?:水平|左右)?\s*翻转",
     "flip_video", {"video_index": 1}),
    (r"^(?:把|将)?\s*(?:第?(\d+)[个号]?)?\s*视频?\s*(?:倒放|倒播|反向播放)",
     "reverse_video", {"video_index": 1}),
    (r"^当前时间|几点了|现在几点",
     "get_current_time", {}),
    (r"^系统信息|系统状态",
     "get_system_info", {}),
]

# 编译缓存
_FAST_PATH_COMPILED: List[Tuple[re.Pattern, str, Dict]] = []

def _get_compiled_rules() -> List[Tuple[re.Pattern, str, Dict]]:
    """懒编译快速通道正则"""
    global _FAST_PATH_COMPILED
    if not _FAST_PATH_COMPILED:
        for pattern, tool_name, extractors in _FAST_PATH_RULES:
            _FAST_PATH_COMPILED.append((re.compile(pattern, re.IGNORECASE), tool_name, extractors))
    return _FAST_PATH_COMPILED

# ==================== 工具链预设 ====================

_TOOL_CHAIN_PRESETS = {
    "多素材混剪": {
        "trigger": r"(?:自动)?混剪|自动剪辑|一键剪辑|批量剪辑",
        "llm_prompt": (
            "用户要做多素材混剪。从用户消息中提取：目标时长(秒,默认30)、风格(默认动感)。\n"
            "输出JSON: {\"duration\": N, \"style\": \"...\"}\n用户消息："
        ),
        "steps": ["list_videos", "smart_clip"],
    },
    "字幕配音": {
        "trigger": r"加字幕.*配音|配音.*加字幕|字幕.*配.*音|完整字幕配音",
        "llm_prompt": (
            "用户要给视频添加字幕和配音。提取：视频序号。\n"
            "输出JSON: {\"video_index\": N}\n用户消息："
        ),
        "steps": ["transcribe_video", "generate_tts", "add_subtitle"],
    },
    "社交导出": {
        "trigger": r"社交.*导出|导出.*社交|抖音.*格式|小红书.*格式|导出.*竖屏",
        "llm_prompt": (
            "用户要导出社交媒体格式视频。提取：平台(抖音/小红书/视频号)。\n"
            "输出JSON: {\"platform\": \"...\"}\n用户消息："
        ),
        "steps": ["cut_video", "compress_video"],
    },
}

# ==================== 批量操作模式 ====================

_BATCH_PATTERNS = {
    "batch_compress": {
        "trigger": r"批量压缩|压缩所有|全部压缩",
    },
    "batch_analyze": {
        "trigger": r"批量分析|分析所有|全部分析",
    },
}

# ==================== 系统提示词 ====================


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
        "5. 剪辑任务时，必须先调用 list_videos 查看项目已有素材，优先使用已有素材。只有素材不足或没有合适的时，才调用 search_material 下载新素材",
        "5.1 search_material 支持逗号分隔多关键词（如 'AI,办公,科技'），一次调用即可搜索多组素材。规划好所有需要的素材类型后，一次性传入所有关键词，避免多次调用浪费轮次",
        "5.2 list_videos 和 search_material 的返回结果已包含素材ID、名称、时长，已足够用于 cut_video/merge_videos 等操作。禁止在 list_videos 或 search_material 之后逐个调用 get_video_detail，这是浪费轮次。get_video_detail 仅在用户明确要求查看某素材详情时使用",
        "6. 尽可能在一轮中同时调用多个互不依赖的工具（例如同时剪切多个视频、同时下载多个素材）。有依赖关系的操作（如先剪切再合并）仍需分轮执行",
        "7. 避免重复调用已获取过的信息，已获取的数据直接使用。能从上下文推断的信息（视频ID、素材ID），直接使用不要问用户",
        "8. 如果素材不匹配需求，直接更换素材或调整方案，不要反复分析同一个不合适的素材",
        "9. 必须使用工具返回的真实数据，严禁编造、猜测或虚构内容",
        "10. 能自动完成的操作直接执行不要问用户：只有一个素材时直接用它；用户说'添加字幕'但没给内容时自动先 transcribe_video 再 add_subtitle；参数有合理默认值时直接使用",
        "11. 工具返回失败时，立即停下来告诉用户失败原因，不要继续调用后续工具浪费算力",
        "",
        "## 当前上下文",
        "",
        "- 项目 ID: " + str(pid),
        "- 项目名: " + str(pname),
        "- 当前日期: " + datetime.now().strftime("%Y年%m月%d日"),
        "",
    ]
    return "\n".join(parts)


def build_comic_system_prompt(tools_description: str, project_id, project_name: str) -> str:
    """构建漫剧模式的系统提示词（最小骨架，流程由扩展注入）"""
    pid = project_id or "无"
    pname = project_name or "无"
    parts = [
        "你是一个 AI 漫剧创作助手。你可以使用以下工具来帮助用户创作漫剧（Comic Drama）。",
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
        "## 规则",
        "",
        "1. 可以在同一条回复中调用多个工具，也可以不调用任何工具直接回复",
        "2. 工具调用后你会收到 <tool_result> 结果，然后继续回复",
        "3. 回复用中文，简洁自然",
        "4. 能从上下文推断的信息直接使用，不要问用户。参数有合理默认值时直接使用",
        "5. 工具返回失败时，立即停下来告诉用户失败原因，不要继续调用后续工具",
        "",
        "## 当前上下文",
        "",
        "- 项目 ID: " + str(pid),
        "- 项目名: " + str(pname),
        "- 当前日期: " + datetime.now().strftime("%Y年%m月%d日"),
        "",
    ]
    return "\n".join(parts)


class ReActAgent:
    """基于 TAOR 循环的对话代理"""

    MAX_ITERATIONS = 15  # 最大循环次数，防止无限循环
    DEEP_RESEARCH_STAGES = ["分析素材", "规划方案", "执行操作"]
    CHECKPOINT_DIR = os.path.join(os.path.expanduser("~"), ".synthetix", "checkpoints")
    ARTIFACTS_DIR = os.path.join(os.path.expanduser("~"), ".synthetix", "artifacts")

    def __init__(self):
        self.sessions = get_session_manager()
        self._confirm_events: Dict[str, asyncio.Event] = {}  # 权限确认事件

    def confirm_tool(self, tool_name: str):
        """外部确认工具执行（由 WebSocket handler 调用）"""
        event = self._confirm_events.get(tool_name)
        if event:
            event.set()

    def _resolve_video_index(self, index_str: Optional[str], state: DialogState) -> Optional[int]:
        """将用户输入的 1-based 索引映射到 last_video_list 中的 video_id"""
        if not index_str or not state.last_video_list:
            return None
        try:
            idx = int(index_str) - 1  # 用户输入从 1 开始
            if 0 <= idx < len(state.last_video_list):
                v = state.last_video_list[idx]
                return v.get("id") or v.get("video_id")
        except (ValueError, TypeError):
            pass
        return None

    async def _try_fast_path(self, user_input: str, state: DialogState) -> Optional[Dict[str, Any]]:
        """尝试快速通道：正则匹配简单指令，直接执行工具，跳过 LLM"""
        text = user_input.strip()
        if len(text) > 100 or len(text) < 2:
            return None

        for regex, tool_name, extractors in _get_compiled_rules():
            m = regex.search(text)
            if not m:
                continue

            # 提取参数
            params = {}
            skip = False
            for param_name, source in extractors.items():
                if isinstance(source, int):
                    val = m.group(source) if source <= len(m.groups()) else None
                    if val is None:
                        skip = True
                        break
                    if param_name == "video_index":
                        video_id = self._resolve_video_index(val, state)
                        if video_id is None:
                            skip = True
                            break
                        params["video_id"] = video_id
                    else:
                        params[param_name] = val.strip()
            if skip:
                continue

            # 填充 project_id
            if state.project_id:
                params["project_id"] = state.project_id

            logger.info(f"[ReAct-FastPath] 命中规则: {tool_name}, params={params}")
            try:
                result = await self._execute_tool(tool_name, params, state)
                # 构造简洁回复
                if result.get("success", True):
                    data = result.get("analysis") or result.get("data") or result.get("output_path") or result.get("videos") or result.get("message", "")
                    if isinstance(data, (list, dict)):
                        reply = json.dumps(data, ensure_ascii=False, default=str)[:500]
                    else:
                        reply = str(data) if data else "操作完成"
                else:
                    reply = f"操作失败: {result.get('error', '未知错误')}"
                return {"reply": reply, "status": "completed", "session_id": state.session_id, "fast_path": True}
            except Exception as e:
                logger.warning(f"[ReAct-FastPath] 快速路径执行失败，回退到 LLM: {e}")
                return None

        return None

    async def _try_tool_chain(self, user_input: str, state: DialogState) -> Optional[Dict[str, Any]]:
        """尝试工具链预设：匹配工作流触发词 → LLM 提参 → 按序执行工具"""
        import re as _re
        text = user_input.strip()

        for chain_name, preset in _TOOL_CHAIN_PRESETS.items():
            if not _re.search(preset["trigger"], text, _re.IGNORECASE):
                continue

            logger.info(f"[ReAct-Chain] 命中工具链: {chain_name}")
            try:
                # 一次快速 LLM 调用提取参数
                from src.application.services.llm_adapter import generate_response_async
                params_text = await asyncio.wait_for(
                    generate_response_async(
                        messages=[
                            {"role": "system", "content": "你是一个参数提取助手。只输出JSON，不输出其他内容。"},
                            {"role": "user", "content": preset["llm_prompt"] + text}
                        ],
                        temperature=0.1, max_tokens=200
                    ),
                    timeout=30
                )
                import json as _json
                try:
                    chain_params = _json.loads(params_text.strip().strip('`'))
                except Exception:
                    chain_params = {}

                if state.project_id:
                    chain_params["project_id"] = state.project_id

                # 按序执行工具链
                results = []
                for step_tool in preset["steps"]:
                    step_params = dict(chain_params)
                    # 从前一步结果提取输入
                    if results:
                        last = results[-1].get("result", {})
                        if "video_id" in last and "video_id" not in step_params:
                            step_params["video_id"] = last["video_id"]
                        if "output_path" in last and "file_path" not in step_params:
                            step_params["file_path"] = last["output_path"]

                    r = await self._execute_tool(step_tool, step_params, state)
                    results.append({"tool": step_tool, "result": r})

                # 构造汇总回复
                summary_parts = []
                for r in results:
                    tool_name = r["tool"]
                    res = r["result"]
                    if res.get("success", True):
                        summary_parts.append(f"{tool_name}: 成功")
                    else:
                        summary_parts.append(f"{tool_name}: 失败 - {res.get('error', '未知')}")

                reply = f"[{chain_name}] 工具链执行完成\n" + "\n".join(summary_parts)
                return {"reply": reply, "status": "completed", "session_id": state.session_id, "tool_chain": chain_name}

            except Exception as e:
                logger.warning(f"[ReAct-Chain] 工具链 {chain_name} 执行失败，回退到 LLM: {e}")
                return None

        return None

    async def _try_batch_route(self, user_input: str, state: DialogState) -> Optional[Dict[str, Any]]:
        """尝试批量操作路由：匹配批量指令 → 列出素材 → 循环执行"""
        import re as _re
        text = user_input.strip()

        for batch_tool, pattern in _BATCH_PATTERNS.items():
            if not _re.search(pattern["trigger"], text, _re.IGNORECASE):
                continue

            logger.info(f"[ReAct-Batch] 命中批量操作: {batch_tool}")
            try:
                # 获取素材列表
                list_params = {}
                if state.project_id:
                    list_params["project_id"] = state.project_id
                list_result = await self._execute_tool("list_videos", list_params, state)

                videos = []
                if list_result.get("success"):
                    videos = list_result.get("videos", list_result.get("data", []))

                if not videos:
                    return {"reply": "没有可操作的素材", "status": "completed", "session_id": state.session_id}

                # 逐个执行
                results = []
                for v in videos:
                    vid = v.get("id") or v.get("video_id")
                    if not vid:
                        continue
                    r = await self._execute_tool(batch_tool, {"video_id": vid}, state)
                    results.append(r)

                success_count = sum(1 for r in results if r.get("success", True))
                reply = f"批量{batch_tool}完成: {success_count}/{len(results)} 成功"
                return {"reply": reply, "status": "completed", "session_id": state.session_id, "batch": True}

            except Exception as e:
                logger.warning(f"[ReAct-Batch] 批量操作 {batch_tool} 失败，回退到 LLM: {e}")
                return None

        return None

    async def _compact_history(self, state: DialogState, max_messages: int = 30) -> bool:
        """智能压缩历史消息：保留最近 15 条 + LLM 摘要"""
        if len(state.history) <= max_messages:
            return False

        recent = state.history[-15:]
        older = state.history[:-15]

        # 用快模型生成摘要
        try:
            summary_messages = [
                {"role": "system", "content": "请将以下对话历史压缩为简洁摘要，保留关键决策、用户偏好和工具调用结果。用中文输出，不超过 300 字。"},
                *older,
                {"role": "user", "content": "请生成摘要"},
            ]
            summary = await asyncio.wait_for(
                generate_response_async(messages=summary_messages, max_tokens=500),
                timeout=60,
            )
            if summary:
                # 用摘要 + 最近消息替换原历史
                state.history = [
                    {"role": "system", "content": f"[历史摘要] {summary.strip()}"},
                    *recent,
                ]
                logger.info(f"[ReAct] 历史压缩: {len(older)} 条旧消息 → 摘要")
                return True
        except Exception as e:
            logger.warning(f"[ReAct] 历史压缩失败: {e}")

        # 降级：硬截断
        state.history = recent
        return False

    def _save_checkpoint(self, session_id: str, stage_idx: int, stage_summaries: list, messages: list):
        """持久化中间结果到检查点文件"""
        os.makedirs(self.CHECKPOINT_DIR, exist_ok=True)
        checkpoint = {
            "session_id": session_id,
            "stage_idx": stage_idx,
            "stage_summaries": stage_summaries,
            "messages": messages[-40:],
            "saved_at": time.time(),
        }
        path = os.path.join(self.CHECKPOINT_DIR, f"{session_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(checkpoint, f, ensure_ascii=False, default=str)
            logger.info(f"[Checkpoint] saved stage {stage_idx} for {session_id}")
        except Exception as e:
            logger.warning(f"[Checkpoint] save failed: {e}")

    def _save_artifact(self, session_id: str, stage_name: str, stage_idx: int, content: Any):
        """Save stage artifact to artifacts directory with meta.json index."""
        session_dir = os.path.join(self.ARTIFACTS_DIR, session_id)
        os.makedirs(session_dir, exist_ok=True)

        artifact_file = os.path.join(session_dir, f"stage_{stage_idx}_{stage_name}.json")
        try:
            with open(artifact_file, "w", encoding="utf-8") as f:
                json.dump({"stage": stage_name, "index": stage_idx, "content": content,
                           "saved_at": time.time()}, f, ensure_ascii=False, default=str)
        except Exception as e:
            logger.warning(f"[Artifact] save failed for stage {stage_idx}: {e}")
            return

        # Update meta.json index
        meta_path = os.path.join(session_dir, "meta.json")
        meta = {"session_id": session_id, "stages": []}
        if os.path.exists(meta_path):
            try:
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass

        stage_entry = {"idx": stage_idx, "name": stage_name, "file": f"stage_{stage_idx}_{stage_name}.json"}
        existing = [s for s in meta["stages"] if s["idx"] != stage_idx]
        existing.append(stage_entry)
        existing.sort(key=lambda s: s["idx"])
        meta["stages"] = existing
        meta["updated_at"] = time.time()

        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
            logger.info(f"[Artifact] saved {stage_name} (stage {stage_idx}) for {session_id}")
        except Exception as e:
            logger.warning(f"[Artifact] meta update failed: {e}")

    def _load_artifacts(self, session_id: str) -> list:
        """Load all artifacts for a session from meta.json index."""
        meta_path = os.path.join(self.ARTIFACTS_DIR, session_id, "meta.json")
        if not os.path.exists(meta_path):
            return []
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            artifacts = []
            for stage in meta.get("stages", []):
                fpath = os.path.join(self.ARTIFACTS_DIR, session_id, stage["file"])
                if os.path.exists(fpath):
                    with open(fpath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    artifacts.append(data)
            return artifacts
        except Exception as e:
            logger.warning(f"[Artifact] load failed: {e}")
            return []

    def _load_checkpoint(self, session_id: str) -> Optional[dict]:
        """加载检查点"""
        path = os.path.join(self.CHECKPOINT_DIR, f"{session_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def _clear_checkpoint(self, session_id: str):
        path = os.path.join(self.CHECKPOINT_DIR, f"{session_id}.json")
        if os.path.exists(path):
            os.remove(path)

    def _resolve_session(self, session_id: Optional[str], project_id: Optional[int] = None) -> DialogState:
        """获取或创建会话，优先按 project_id 恢复历史会话"""
        if session_id:
            state = self.sessions.get_session(session_id)
            if state:
                return state
        if project_id:
            state = self.sessions.restore_last_session(project_id)
            if state:
                logger.info(f"[ReAct] 恢复项目 {project_id} 的历史会话 {state.session_id}")
                return state
        return self.sessions.create_session()

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
        # 获取或创建会话（优先恢复历史会话）
        project_id = context.get("project_id") if context else None
        state = self._resolve_session(session_id, project_id)
        state.add_message("user", user_input)

        # 合并上下文
        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)
                state.metadata["project_id"] = state.project_id
            attachments = context.get("attachments")
            if attachments:
                state.metadata["pending_attachments"] = attachments
            # 首次设置模式（默认 video 不被覆盖）
            mode_val = context.get("mode")
            if mode_val and state.mode == "video":
                state.mode = mode_val

        logger.info(f"[ReAct] 用户输入: '{user_input}', project_id={state.project_id}")

        # 快速通道：简单指令直接执行，跳过 LLM
        fast_result = await self._try_fast_path(user_input, state)
        if fast_result is not None:
            state.add_message("assistant", fast_result["reply"])
            self.sessions.persist_session(state)
            return fast_result

        # 工具链预设：匹配工作流一键执行
        chain_result = await self._try_tool_chain(user_input, state)
        if chain_result is not None:
            state.add_message("assistant", chain_result["reply"])
            self.sessions.persist_session(state)
            return chain_result

        # 批量操作路由：一次 LLM 提参 + 代码循环
        batch_result = await self._try_batch_route(user_input, state)
        if batch_result is not None:
            state.add_message("assistant", batch_result["reply"])
            self.sessions.persist_session(state)
            return batch_result

        try:
            # TAOR 循环
            final_reply, tool_summary = await self._taor_loop(state, user_input)

            reply_with_context = final_reply
            if tool_summary:
                reply_with_context += f"\n\n[工具执行记录]\n{tool_summary}"

            state.add_message("assistant", reply_with_context)
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
        project_id = context.get("project_id") if context else None
        state = self._resolve_session(session_id, project_id)
        state.add_message("user", user_input)

        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)
                state.metadata["project_id"] = state.project_id
            attachments = context.get("attachments")
            if attachments:
                state.metadata["pending_attachments"] = attachments
            # 首次设置模式（默认 video 不被覆盖）
            mode_val = context.get("mode")
            if mode_val and state.mode == "video":
                state.mode = mode_val
            # 按需激活的扩展列表（@ 流水线触发）
            active_ext = context.get("active_extensions")
            if active_ext:
                state.metadata["active_extensions"] = active_ext

        yield {"type": "session", "session_id": state.session_id}
        logger.info(f"[ReAct-Stream] 用户输入: '{user_input}', project_id={state.project_id}")

        # 快速通道：简单指令直接执行，跳过 LLM
        fast_result = await self._try_fast_path(user_input, state)
        if fast_result is not None:
            yield {"type": "reply", "content": fast_result["reply"]}
            yield {"type": "done", "status": "completed", "session_id": state.session_id, "fast_path": True}
            state.add_message("assistant", fast_result["reply"])
            self.sessions.persist_session(state)
            return

        # 工具链预设
        chain_result = await self._try_tool_chain(user_input, state)
        if chain_result is not None:
            yield {"type": "reply", "content": chain_result["reply"]}
            yield {"type": "done", "status": "completed", "session_id": state.session_id, "tool_chain": chain_result.get("tool_chain")}
            state.add_message("assistant", chain_result["reply"])
            self.sessions.persist_session(state)
            return

        # 批量操作路由
        batch_result = await self._try_batch_route(user_input, state)
        if batch_result is not None:
            yield {"type": "reply", "content": batch_result["reply"]}
            yield {"type": "done", "status": "completed", "session_id": state.session_id, "batch": True}
            state.add_message("assistant", batch_result["reply"])
            self.sessions.persist_session(state)
            return

        pending_tasks: set = set()
        _supplemented_tools: set = set()  # 已动态补充参数描述的工具
        try:
            # 历史过长时触发压缩
            await self._compact_history(state)
            messages = self._build_messages(state)
            final_reply = ""

            has_temp_asset = False
            all_tool_results = []  # 收集所有轮次的工具结果
            kv_session_id = None  # KV Cache session_id

            for iteration in range(self.MAX_ITERATIONS):
                yield {"type": "thinking", "iteration": iteration + 1}

                model = select_model(messages, iteration=iteration)
                provider_options = {"use_kv_cache": True}
                if kv_session_id:
                    provider_options["session_id"] = kv_session_id

                response_text = await asyncio.wait_for(
                    generate_response_async(
                        messages=messages,
                        model_name=model,
                        temperature=0.7,
                        max_tokens=2048,
                        provider_options=provider_options,
                    ),
                    timeout=LLM_TIMEOUT,
                )

                # 提取 session_id 供下一轮 KV Cache 使用
                client = get_client()
                kv_session_id = client.last_response.get("output", {}).get("session_id") or kv_session_id
                cached_tokens = client.last_response.get("usage", {}).get("cached_tokens", 0)
                if cached_tokens:
                    logger.info(f"[ReAct-Stream] KV Cache 命中 {cached_tokens} tokens")

                tool_calls = self._parse_tool_calls(response_text)

                if not tool_calls:
                    final_reply = self._strip_tool_call_hints(response_text)
                    if not final_reply.strip() and has_temp_asset:
                        # 有临时素材但 LLM 没有文字回复，用 LLM 原始输出作为回复
                        final_reply = response_text.strip()
                    if not final_reply.strip():
                        final_reply = "处理完成。"
                    yield {"type": "reply", "content": final_reply}
                    break

                # 执行工具并推送状态
                tool_results = []

                # 判断是否可以并行执行（需要特殊处理的工具走串行）
                needs_special = any(tc["name"] == "download_video" for tc in tool_calls)

                if len(tool_calls) > 1 and not needs_special:
                    # 并行执行：先推送所有 tool_start，再 gather，再依次推送结果
                    for tc in tool_calls:
                        tool = registry.get_tool(tc["name"])
                        perm = tool.permission if tool else "modify"
                        yield {"type": "tool_start", "tool": tc["name"], "params": tc["params"], "permission": perm}
                        logger.debug(f"[ToolExec] >>> {tc['name']}(...) [parallel]")

                    tasks = [self._execute_tool(tc["name"], tc["params"], state) for tc in tool_calls]
                    results = await asyncio.gather(*tasks, return_exceptions=True)

                    for tc, result in zip(tool_calls, results):
                        if isinstance(result, Exception):
                            result = {"success": False, "error": str(result)}
                        tool_name = tc["name"]
                        tool_params = tc["params"]

                        logger.debug(f"[ToolExec] <<< {tool_name} success={result.get('success', True)}")

                        if result.get("is_temp_asset"):
                            has_temp_asset = True

                        tool_results.append({"name": tool_name, "params": tool_params, "result": result})
                        all_tool_results.append({"name": tool_name, "params": tool_params, "result": result})

                        if tool_name == "list_videos" and result.get("videos"):
                            state.last_video_list = result["videos"]
                        vid_param = tool_params.get("video_id")
                        if vid_param and isinstance(vid_param, int):
                            state.last_referenced_video_id = vid_param
                        if result.get("video_id"):
                            state.last_referenced_video_id = result["video_id"]

                        result_preview = json.dumps(result, ensure_ascii=False, default=str)
                        if len(result_preview) > 500:
                            result_preview = result_preview[:500] + "...(已截断)"

                        media_info = None
                        if result.get("is_temp_asset") or result.get("web_path"):
                            media_info = {
                                "web_path": result.get("web_path"),
                                "output_path": result.get("output_path"),
                                "output_type": result.get("output_type", "video"),
                                "duration": result.get("duration"),
                                "video_id": result.get("video_id"),
                                "temp_file_id": result.get("temp_file_id"),
                            }

                        yield {"type": "tool_result", "tool": tool_name, "success": result.get("success", True), "preview": result_preview, "media_info": media_info}
                else:
                    # 串行执行（download_video 等需要特殊处理的工具）
                    for tc in tool_calls:
                        tool_name = tc["name"]
                        tool_params = tc["params"]

                        tool = registry.get_tool(tool_name)
                        perm = tool.permission if tool else "modify"

                        yield {"type": "tool_start", "tool": tool_name, "params": tool_params, "permission": perm}
                        logger.debug(f"[ToolExec] >>> {tool_name}(...)")

                        if tool_name == "download_video":
                            progress_dict = {}
                            tool_task = asyncio.ensure_future(
                                self._execute_tool(tool_name, tool_params, state, progress_dict=progress_dict)
                            )
                            pending_tasks.add(tool_task)
                            tool_task.add_done_callback(pending_tasks.discard)
                            while not tool_task.done():
                                p = {k: v for k, v in progress_dict.items() if v}
                                if p:
                                    yield {"type": "tool_progress", "tool": tool_name, **p}
                                await asyncio.sleep(0.8)
                            result = tool_task.result()
                        else:
                            tool_task = asyncio.ensure_future(
                                self._execute_tool(tool_name, tool_params, state)
                            )
                            pending_tasks.add(tool_task)
                            tool_task.add_done_callback(pending_tasks.discard)
                            while not tool_task.done():
                                yield {"type": "heartbeat"}
                                await asyncio.sleep(3)
                            result = tool_task.result()

                        logger.debug(f"[ToolExec] <<< {tool_name} success={result.get('success', True)}")

                        if result.get("is_temp_asset"):
                            has_temp_asset = True

                        tool_results.append({"name": tool_name, "params": tool_params, "result": result})
                        all_tool_results.append({"name": tool_name, "params": tool_params, "result": result})

                        if tool_name == "list_videos" and result.get("videos"):
                            state.last_video_list = result["videos"]
                        vid_param = tool_params.get("video_id")
                        if vid_param and isinstance(vid_param, int):
                            state.last_referenced_video_id = vid_param
                        if result.get("video_id"):
                            state.last_referenced_video_id = result["video_id"]

                        result_preview = json.dumps(result, ensure_ascii=False, default=str)
                        if len(result_preview) > 500:
                            result_preview = result_preview[:500] + "...(已截断)"

                        media_info = None
                        if result.get("is_temp_asset") or result.get("web_path"):
                            media_info = {
                                "web_path": result.get("web_path"),
                                "output_path": result.get("output_path"),
                                "output_type": result.get("output_type", "video"),
                                "duration": result.get("duration"),
                                "video_id": result.get("video_id"),
                                "temp_file_id": result.get("temp_file_id"),
                            }

                        yield {"type": "tool_result", "tool": tool_name, "success": result.get("success", True), "preview": result_preview, "media_info": media_info}

                # Observe
                messages.append({"role": "assistant", "content": response_text})
                observation = self._format_observations(tool_results)
                messages.append({"role": "user", "content": observation})

                # 动态补充非核心工具的完整参数描述
                for tc in tool_calls:
                    tname = tc["name"]
                    if tname not in registry.CORE_TOOLS and tname not in _supplemented_tools:
                        full_desc = registry.get_tool_full_description(tname)
                        if full_desc:
                            messages.append({"role": "system", "content":
                                f"[工具参数补充] {tname} 的完整参数：\n\n{full_desc}"})
                            _supplemented_tools.add(tname)
            else:
                # 超过最大循环次数
                final_reply = response_text if response_text else "处理超时，请简化您的问题后重试。"
                yield {"type": "reply", "content": final_reply}

            reply_with_context = final_reply
            tool_summary = self._build_tool_summary(all_tool_results)
            if tool_summary:
                reply_with_context += f"\n\n[工具执行记录]\n{tool_summary}"

            state.add_message("assistant", reply_with_context)
            self.sessions.persist_session(state)

            # 从本次对话中提取偏好并保存
            if state.project_id:
                try:
                    new_prefs = await extract_preferences_from_messages(state.history[-10:])
                    if new_prefs:
                        memory = get_project_memory(state.project_id)
                        for k, v in new_prefs.items():
                            memory.set_preference(k, v)
                except Exception:
                    pass

            yield {"type": "done", "status": "completed", "session_id": state.session_id}

        except asyncio.CancelledError:
            # SSE 客户端断连，取消所有进行中的工具任务
            logger.info(f"[ReAct-Stream] 客户端断连，取消 {len(pending_tasks)} 个待处理任务")
            for task in pending_tasks:
                if not task.done():
                    task.cancel()
            if pending_tasks:
                await asyncio.gather(*pending_tasks, return_exceptions=True)
            yield {"type": "done", "status": "cancelled", "session_id": state.session_id}

        except Exception as e:
            logger.error(f"[ReAct-Stream] 处理失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e), "session_id": state.session_id}

    async def process_deep_research(
        self,
        session_id: Optional[str],
        user_input: str,
        context: Optional[Dict] = None,
    ):
        """
        深度研究模式：多阶段分析→规划→执行

        每阶段独立运行 TAOR 循环，阶段间传递总结。
        适用于复杂剪辑需求（如"做一个完整的短视频"）。
        """
        project_id = context.get("project_id") if context else None
        state = self._resolve_session(session_id, project_id)
        state.add_message("user", user_input)

        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)
                state.metadata["project_id"] = state.project_id
            attachments = context.get("attachments")
            if attachments:
                state.metadata["pending_attachments"] = attachments
            # 首次设置模式（默认 video 不被覆盖）
            mode_val = context.get("mode")
            if mode_val and state.mode == "video":
                state.mode = mode_val

        yield {"type": "deep_research", "stage": "start", "total_stages": len(self.DEEP_RESEARCH_STAGES)}

        # Check for existing checkpoint to resume
        checkpoint = self._load_checkpoint(state.session_id)
        if checkpoint and checkpoint.get("stage_idx", 0) > 0:
            start_stage = checkpoint["stage_idx"] + 1
            stage_summaries = checkpoint.get("stage_summaries", [])
            await self._compact_history(state)
            messages = checkpoint.get("messages", self._build_messages(state))
            yield {"type": "deep_research", "stage": "resume", "resumed_from": start_stage}
            logger.info(f"[DeepResearch] resuming from stage {start_stage}")
        else:
            start_stage = 0
            stage_summaries = []
            messages = self._build_messages(state)

        try:
            for i in range(start_stage, len(self.DEEP_RESEARCH_STAGES)):
                stage_name = self.DEEP_RESEARCH_STAGES[i]
                yield {
                    "type": "deep_research",
                    "stage": i + 1,
                    "stage_name": stage_name,
                    "total_stages": len(self.DEEP_RESEARCH_STAGES),
                }

                # 构造阶段提示
                prev_context = ""
                if stage_summaries:
                    prev_context = "\n\n## 前序阶段总结\n" + "\n".join(
                        f"### {name}\n{summary}"
                        for name, summary in stage_summaries
                    )

                stage_prompt = (
                    f"[阶段 {i+1}/{len(self.DEEP_RESEARCH_STAGES)}: {stage_name}]\n"
                    f"用户需求: {user_input}\n"
                    f"请专注于完成「{stage_name}」阶段的工作。"
                    f"{prev_context}"
                )

                messages.append({"role": "user", "content": stage_prompt})

                # 运行 TAOR 循环
                stage_reply = ""
                kv_session_id = None
                _dr_supplemented: set = set()  # 深度研究内补充过的工具
                for iteration in range(self.MAX_ITERATIONS):
                    yield {"type": "thinking", "iteration": iteration + 1, "stage": stage_name}

                    model = select_model(messages, iteration=iteration)
                    provider_options = {"use_kv_cache": True}
                    if kv_session_id:
                        provider_options["session_id"] = kv_session_id

                    response_text = await asyncio.wait_for(
                        generate_response_async(
                            messages=messages, model_name=model, temperature=0.7, max_tokens=2048,
                            provider_options=provider_options,
                        ),
                        timeout=LLM_TIMEOUT,
                    )

                    # 提取 session_id 供下一轮 KV Cache 使用
                    client = get_client()
                    kv_session_id = client.last_response.get("output", {}).get("session_id") or kv_session_id
                    cached_tokens = client.last_response.get("usage", {}).get("cached_tokens", 0)
                    if cached_tokens:
                        logger.info(f"[DeepResearch] KV Cache 命中 {cached_tokens} tokens")

                    tool_calls = self._parse_tool_calls(response_text)
                    if not tool_calls:
                        stage_reply = self._strip_tool_call_hints(response_text)
                        break

                    # 执行工具
                    tool_results = []
                    for tc in tool_calls:
                        yield {"type": "tool_start", "tool": tc["name"], "params": tc["params"], "stage": stage_name}
                        logger.debug(f"[ToolExec] >>> {tc['name']}(...)")
                        result = await self._execute_tool(tc["name"], tc["params"], state)
                        logger.debug(f"[ToolExec] <<< {tc['name']} success={result.get('success', True)}")
                        tool_results.append({"name": tc["name"], "params": tc["params"], "result": result})

                        dr_media_info = None
                        if result.get("is_temp_asset") or result.get("web_path"):
                            dr_media_info = {
                                "web_path": result.get("web_path"),
                                "output_path": result.get("output_path"),
                                "output_type": result.get("output_type", "video"),
                                "duration": result.get("duration"),
                                "video_id": result.get("video_id"),
                                "temp_file_id": result.get("temp_file_id"),
                            }

                        yield {"type": "tool_result", "tool": tc["name"], "success": result.get("success", True), "media_info": dr_media_info}

                    messages.append({"role": "assistant", "content": response_text})
                    observation = self._format_observations(tool_results)
                    messages.append({"role": "user", "content": observation})

                    # 动态补充非核心工具的完整参数描述
                    for tc in tool_calls:
                        tname = tc["name"]
                        if tname not in registry.CORE_TOOLS and tname not in _dr_supplemented:
                            full_desc = registry.get_tool_full_description(tname)
                            if full_desc:
                                messages.append({"role": "system", "content":
                                    f"[工具参数补充] {tname} 的完整参数：\n\n{full_desc}"})
                                _dr_supplemented.add(tname)

                if not stage_reply:
                    stage_reply = response_text if response_text else "本阶段无输出"

                stage_summaries.append((stage_name, stage_reply[:500]))
                yield {"type": "stage_result", "stage": stage_name, "summary": stage_reply[:500]}

                # Save checkpoint after each completed stage
                self._save_checkpoint(state.session_id, i, stage_summaries, messages)
                # Save artifact for crash recovery
                self._save_artifact(state.session_id, stage_name, i, {
                    "summary": stage_reply[:2000],
                    "tool_calls": [tr["name"] for tr in tool_results] if tool_results else [],
                })

            # 最终综合回复
            final_prompt = (
                f"所有阶段已完成。请基于以下总结，用自然语言向用户汇报最终结果。\n\n"
                + "\n".join(f"## {n}\n{s}" for n, s in stage_summaries)
            )
            final_reply = await asyncio.wait_for(
                generate_response_async(
                    messages=[{"role": "user", "content": final_prompt}],
                    temperature=0.7, max_tokens=2048,
                ),
                timeout=LLM_TIMEOUT,
            )

            state.add_message("assistant", final_reply)
            self.sessions.persist_session(state)
            self._clear_checkpoint(state.session_id)
            yield {"type": "reply", "content": final_reply}
            yield {"type": "done", "status": "completed", "session_id": state.session_id}

        except asyncio.CancelledError:
            logger.info(f"[DeepResearch] 客户端断连，清理资源")
            raise

        except Exception as e:
            logger.error(f"[DeepResearch] 失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e), "session_id": state.session_id}

    async def process_plan_stream(
        self,
        session_id: Optional[str],
        user_input: str,
        context: Optional[Dict] = None,
    ):
        """
        计划模式：一次 LLM 调用生成执行计划 → 用户确认 → 按序执行。

        SSE 事件流:
        - session: 会话信息
        - thinking: LLM 正在生成计划
        - plan: 计划内容（summary + steps）
        - plan_step_start / plan_step_result / plan_step_confirm: 执行过程
        - plan_done: 计划执行完成
        - reply: 最终总结
        - done: 处理完成
        - error: 处理出错
        """
        from src.agent.plan_generator import generate_plan_from_llm
        from src.agent.plan_executor import PlanExecutor

        project_id = context.get("project_id") if context else None
        state = self._resolve_session(session_id, project_id)
        state.add_message("user", user_input)

        if context:
            pid = context.get("project_id")
            if pid:
                state.project_id = int(pid)
                state.metadata["project_id"] = state.project_id
            attachments = context.get("attachments")
            if attachments:
                state.metadata["pending_attachments"] = attachments
            mode_val = context.get("mode")
            if mode_val and state.mode == "video":
                state.mode = mode_val

        yield {"type": "session", "session_id": state.session_id}

        try:
            # Phase 1: LLM 生成计划
            yield {"type": "thinking", "iteration": 1, "message": "正在规划执行方案..."}

            plan_data = await generate_plan_from_llm(
                user_input=user_input,
                state=state,
                mode=getattr(state, 'mode', 'video'),
            )

            plan_id = plan_data.get("plan_id", f"plan_{int(time.time())}")
            steps = plan_data.get("steps", [])
            summary = plan_data.get("summary", "")

            if not steps:
                # LLM 未能生成有效计划，降级为普通回复
                raw = plan_data.get("raw", summary)
                yield {"type": "reply", "content": raw or "抱歉，无法生成执行计划。"}
                yield {"type": "done", "status": "completed", "session_id": state.session_id}
                state.add_message("assistant", raw or "无法生成执行计划")
                self.sessions.persist_session(state)
                return

            # yield 计划事件，等待前端确认
            yield {
                "type": "plan",
                "plan_id": plan_id,
                "summary": summary,
                "steps": steps,
                "total_steps": len(steps),
            }

            # 存储计划到会话元数据
            state.metadata["_pending_plan"] = plan_data
            state.metadata["_plan_confirmed"] = False
            state.metadata["_plan_cancelled"] = False
            self.sessions.persist_session(state)

            # Phase 2: 等待用户确认
            confirm_timeout = 300  # 5 分钟等待确认
            elapsed = 0
            check_interval = 0.5
            while elapsed < confirm_timeout:
                if state.metadata.get("_plan_cancelled"):
                    yield {"type": "reply", "content": "方案已取消。"}
                    yield {"type": "plan_done", "status": "cancelled", "completed_steps": 0, "total_steps": len(steps)}
                    yield {"type": "done", "status": "completed", "session_id": state.session_id}
                    state.add_message("assistant", "用户取消了执行方案")
                    self.sessions.persist_session(state)
                    return
                if state.metadata.get("_plan_confirmed"):
                    break
                await asyncio.sleep(check_interval)
                elapsed += check_interval
            else:
                # 确认超时
                yield {"type": "reply", "content": "方案确认超时，请重新发送。"}
                yield {"type": "plan_done", "status": "timeout", "completed_steps": 0, "total_steps": len(steps)}
                yield {"type": "done", "status": "completed", "session_id": state.session_id}
                state.add_message("assistant", "方案确认超时")
                self.sessions.persist_session(state)
                return

            # Phase 3: 执行计划
            executor = PlanExecutor(self)
            from src.agent.plan_executor import PlanStep

            plan_steps = [
                PlanStep(
                    id=s["id"],
                    tool=s["tool"],
                    params=s["params"],
                    description=s["description"],
                    risk=s.get("risk", "safe"),
                    estimated_time=s.get("estimated_time"),
                )
                for s in steps
            ]

            all_results = []
            async for event in executor.execute_plan_stream(plan_steps, state):
                if event["type"] == "plan_done":
                    # 计划执行完成，构建最终回复
                    completed = event.get("completed_steps", 0)
                    total = event.get("total_steps", len(steps))
                    final_status = event.get("status", "completed")

                    if final_status == "completed":
                        reply_text = f"执行完成！共 {total} 步，成功 {completed} 步。\n\n{summary}"
                    elif final_status == "cancelled":
                        reply_text = f"执行已取消。已完成 {completed}/{total} 步。"
                    else:
                        reply_text = f"执行异常。已完成 {completed}/{total} 步。"

                    yield {"type": "reply", "content": reply_text}
                    yield event  # plan_done

                    # 持久化
                    state.add_message("assistant", reply_text)
                    self.sessions.persist_session(state)

                    # 提取偏好
                    if state.project_id:
                        try:
                            new_prefs = await extract_preferences_from_messages(state.history[-10:])
                            if new_prefs:
                                memory = get_project_memory(state.project_id)
                                for k, v in new_prefs.items():
                                    memory.set_preference(k, v)
                        except Exception:
                            pass

                    yield {"type": "done", "status": "completed", "session_id": state.session_id}
                    return
                else:
                    yield event

        except asyncio.CancelledError:
            logger.info("[PlanStream] 客户端断连")
            state.metadata["_plan_cancelled"] = True
            yield {"type": "done", "status": "cancelled", "session_id": state.session_id}

        except Exception as e:
            logger.error(f"[PlanStream] 失败: {e}", exc_info=True)
            yield {"type": "error", "message": str(e), "session_id": state.session_id}

    async def _taor_loop(self, state: DialogState, user_input: str):
        """
        TAOR 主循环: Think → Act → Observe → Repeat

        每轮将历史消息 + 工具结果发送给 LLM，
        LLM 要么直接回复用户，要么输出 <tool_call/> 调用工具。
        如果有工具调用，执行后把结果加入消息历史，继续下一轮。

        Returns: (final_reply, tool_summary)
        """
        # 构建消息历史（最近 20 条）
        messages = self._build_messages(state)
        has_temp_asset = False
        all_tool_results = []  # 收集所有轮次的工具结果
        kv_session_id = None  # KV Cache session_id，跨迭代复用
        _supplemented_tools: set = set()  # 已动态补充参数描述的工具

        for iteration in range(self.MAX_ITERATIONS):
            logger.info(f"[ReAct] 第{iteration+1}轮循环")

            # Think: 调用 LLM（快慢双脑路由 + KV Cache）
            model = select_model(messages, iteration=iteration)
            provider_options = {"use_kv_cache": True}
            if kv_session_id:
                provider_options["session_id"] = kv_session_id

            response_text = None
            for retry in range(LLM_MAX_RETRIES + 1):
                try:
                    response_text = await asyncio.wait_for(
                        generate_response_async(
                            messages=messages,
                            model_name=model,
                            temperature=0.7,
                            max_tokens=2048,
                            provider_options=provider_options,
                        ),
                        timeout=LLM_TIMEOUT,
                    )
                    break
                except (asyncio.TimeoutError, Exception) as llm_err:
                    if retry < LLM_MAX_RETRIES:
                        logger.warning("[ReAct] LLM 调用失败 (retry=%d/%d): %s", retry + 1, LLM_MAX_RETRIES, llm_err)
                        await asyncio.sleep(LLM_RETRY_DELAY * (retry + 1))
                    else:
                        raise
            if response_text is None:
                raise RuntimeError("LLM 返回空响应")

            # 提取 session_id 供下一轮 KV Cache 使用
            client = get_client()
            kv_session_id = client.last_response.get("output", {}).get("session_id") or kv_session_id
            cached_tokens = client.last_response.get("usage", {}).get("cached_tokens", 0)
            if cached_tokens:
                logger.info(f"[ReAct] KV Cache 命中 {cached_tokens} tokens")

            logger.info(f"[ReAct] LLM响应 (前200字): {response_text[:200]}")

            # 解析工具调用
            tool_calls = self._parse_tool_calls(response_text)

            if not tool_calls:
                # 无工具调用 → 循环结束，直接回复用户
                clean_reply = self._strip_tool_call_hints(response_text)
                # 有临时素材产出时跳过冗余文字
                if has_temp_asset and clean_reply:
                    return "", self._build_tool_summary(all_tool_results)
                return clean_reply, self._build_tool_summary(all_tool_results)

            # Act: 执行工具调用
            tool_results = []
            for tc in tool_calls:
                logger.debug(f"[ToolExec] >>> {tc['name']}(...)")
                result = await self._execute_tool(tc["name"], tc["params"], state)
                _res_preview = json.dumps(result, ensure_ascii=False, default=str)[:300]
                logger.debug(f"[ToolExec] <<< {tc['name']} success={result.get('success', True)}")

                if result.get("is_temp_asset"):
                    has_temp_asset = True

                tool_results.append({
                    "name": tc["name"],
                    "params": tc["params"],
                    "result": result,
                })
                all_tool_results.append({
                    "name": tc["name"],
                    "params": tc["params"],
                    "result": result,
                })

                # 缓存视频列表供序数解析
                if tc["name"] == "list_videos" and result.get("videos"):
                    state.last_video_list = result["videos"]

                # 跟踪最近引用的素材 ID
                vid_param = tc["params"].get("video_id")
                if vid_param and isinstance(vid_param, int):
                    state.last_referenced_video_id = vid_param
                if result.get("video_id"):
                    state.last_referenced_video_id = result["video_id"]

            # Observe: 将 LLM 回复 + 工具结果加入消息历史
            messages.append({"role": "assistant", "content": response_text})
            observation = self._format_observations(tool_results)
            messages.append({"role": "user", "content": observation})
            logger.info(f"[ReAct] 观察: {observation[:300]}")

            # 动态补充非核心工具的完整参数描述
            for tc in tool_calls:
                tname = tc["name"]
                if tname not in registry.CORE_TOOLS and tname not in _supplemented_tools:
                    full_desc = registry.get_tool_full_description(tname)
                    if full_desc:
                        messages.append({"role": "system", "content":
                            f"[工具参数补充] {tname} 的完整参数：\n\n{full_desc}"})
                        _supplemented_tools.add(tname)

        # 超过最大循环次数
        reply = "" if has_temp_asset else (response_text if response_text else "处理超时，请简化您的问题后重试。")
        return reply, self._build_tool_summary(all_tool_results)

    def _build_messages(self, state: DialogState) -> List[Dict[str, str]]:
        """构建发送给 LLM 的消息列表"""
        # 按模式过滤工具
        mode = getattr(state, 'mode', 'video')
        active_ext = state.metadata.get("active_extensions") if hasattr(state, 'metadata') else None

        # 根据是否有激活的扩展，选择工具描述策略
        if active_ext and len(active_ext) > 0:
            # @ 模板模式：只注入模板所需的工具
            tool_names = set()
            for ext_name in active_ext:
                try:
                    from src.agent.extension_loader import get_extension_tools
                    tool_names |= get_extension_tools(ext_name)
                except Exception:
                    pass
            # 合并运行时用户自定义的额外工具
            runtime_tools = state.metadata.get("pipeline_required_tools", [])
            if runtime_tools:
                tool_names |= set(runtime_tools)
            if tool_names:
                tools_desc = registry.get_tools_description_filtered(tool_names)
            else:
                tools_desc = registry.get_tools_description_by_category(mode)
        else:
            # 普通对话模式：核心工具完整描述 + 其他工具仅名称
            tools_desc = registry.get_tools_description_condensed(mode)
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

        if mode == "comic":
            system_prompt = build_comic_system_prompt(tools_desc, state.project_id, project_name)
        else:
            system_prompt = build_system_prompt(tools_desc, state.project_id, project_name)

        # 注入项目偏好记忆（相关性评分 + 字符预算）
        if state.project_id:
            try:
                memory = get_project_memory(state.project_id)
                # 用最近用户消息作为查询上下文
                query = ""
                for msg in reversed(state.history):
                    if msg.get("role") == "user":
                        query = msg.get("content", "")[:200]
                        break
                pref_summary = memory.get_relevant_summary(query=query)
                if pref_summary:
                    system_prompt += f"\n\n## 用户偏好（基于历史对话自动记录）\n\n{pref_summary}"
            except Exception:
                pass

        # 注入扩展提示词（system 级常驻 + 按需激活的 user 级）
        try:
            from src.agent.extension_loader import get_extensions_prompt_section
            active_ext = state.metadata.get("active_extensions") if hasattr(state, 'metadata') else None
            ext_section = get_extensions_prompt_section(current_mode=mode, active_extensions=active_ext)
            if ext_section:
                system_prompt += f"\n\n{ext_section}"
        except Exception:
            pass

        # 注入 MCP 外部工具描述
        try:
            from src.agent.mcp_client import mcp_client
            mcp_desc = mcp_client.get_tools_description()
            if mcp_desc:
                system_prompt += f"\n\n{mcp_desc}"
        except Exception:
            pass

        messages = [{"role": "system", "content": system_prompt}]

        # 历史消息（最近 20 条）
        history = state.history[-20:] if state.history else []
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # 注入当前上下文（最近操作的素材 ID、素材清单等）
        context_parts = []
        if state.last_referenced_video_id:
            context_parts.append(f"最近操作的素材ID: {state.last_referenced_video_id}（用户说'这张图片'、'这个视频'等指代时默认使用此ID）")
        if state.last_video_list:
            asset_lines = []
            for i, v in enumerate(state.last_video_list[-10:]):
                name = v.get("name", v.get("video_name", "未命名"))
                vid = v.get("id", "?")
                ft = v.get("file_type", "video")
                asset_lines.append(f"  {i+1}. {name} (ID: {vid}, 类型: {ft})")
            if asset_lines:
                context_parts.append("项目素材清单:\n" + "\n".join(asset_lines))
        if context_parts:
            messages.append({"role": "system", "content": "[当前上下文]\n" + "\n".join(context_parts)})

        # 会话恢复提示（重启后注入一次）
        if state.metadata.get("_restored_from_db"):
            messages.append({"role": "system", "content": (
                "注意：本次会话是从之前的对话中恢复的（服务可能重启过）。"
                "上方历史记录和当前上下文中包含了之前的素材信息，"
                "请据此继续对话，不要重复询问已有信息。"
            )})
            state.metadata.pop("_restored_from_db", None)

        # 注入用户上传的附件信息
        pending = state.metadata.pop("pending_attachments", None)
        if pending:
            att_desc = "用户上传了以下素材：\n"
            for att in pending:
                file_type = att.get("type", "file")
                name = att.get("name", "未知文件")
                local_path = att.get("localPath", "")
                vid = att.get("videoId") or att.get("video_id")
                line = f"- {file_type}文件: {name} (本地路径: {local_path}"
                if vid:
                    line += f", 素材ID: {vid}"
                line += ")\n"
                att_desc += line
            att_desc += "请根据用户的需求，使用对应工具对素材进行操作。素材ID可直接作为工具的 video_id 参数使用。"
            messages.append({"role": "user", "content": att_desc})

        return messages

    def _parse_tool_calls(self, text: str) -> List[Dict[str, Any]]:
        """
        解析 LLM 响应中的工具调用

        格式: <tool_call name="tool_name">\n{"key": "value"}\n</tool_call}>
        """
        calls = []
        matches = re.findall(TOOL_CALL_PATTERN, text, re.DOTALL)

        for name, params_str in matches:
            try:
                params = json.loads(params_str.strip())
            except (json.JSONDecodeError, ValueError) as parse_err:
                logger.warning("[ReAct] JSON 解析失败 (tool=%s): %s, raw: %.200s", name, parse_err, params_str)
                params = {"_parse_error": f"JSON 格式错误，请修正后重试。原始内容: {params_str[:200]}"}
            calls.append({"name": name.strip(), "params": params})

        return calls

    async def _execute_tool(
        self, tool_name: str, params: Dict, state: DialogState,
        progress_dict: Dict = None,
    ) -> Dict[str, Any]:
        """执行单个工具（支持 registry 工具和 MCP 外部工具）"""
        logger.info(f"[_execute_tool] tool={tool_name}, params={json.dumps(params, ensure_ascii=False, default=str)[:200]}")
        tool = registry.get_tool(tool_name)

        # 权限门控：modify/destructive 工具需确认
        if tool and tool.permission in ("modify", "destructive"):
            confirm_key = f"{tool_name}_{id(params)}"
            confirm_event = asyncio.Event()
            self._confirm_events[confirm_key] = confirm_event
            confirm_timeout = 5 if tool.permission == "modify" else 10
            logger.warning(f"[ReAct] {tool.permission} 工具 {tool_name} 等待确认...")
            try:
                await asyncio.wait_for(confirm_event.wait(), timeout=confirm_timeout)
            except asyncio.TimeoutError:
                logger.warning(f"[ReAct] {tool.permission} 工具 {tool_name} 确认超时，自动执行")
            finally:
                self._confirm_events.pop(confirm_key, None)

        # 尝试 MCP 外部工具
        if not tool:
            try:
                from src.agent.mcp_client import mcp_client
                if tool_name in mcp_client.tools:
                    logger.info(f"[ReAct] 调用 MCP 工具: {tool_name}")
                    return await mcp_client.call_tool(tool_name, params)
            except Exception as e:
                logger.warning(f"[ReAct] MCP 工具调用失败: {e}")

            return {"success": False, "error": f"未知工具: {tool_name}"}

        # 注入 project_id
        if state.project_id and "project_id" not in params:
            params["project_id"] = state.project_id

        # 注入 progress_dict（供支持进度的工具使用）
        if progress_dict is not None:
            params["_progress_dict"] = progress_dict

        try:
            # 参数校验
            logger.debug(f"[_execute_tool] {tool_name} params={json.dumps(params, ensure_ascii=False, default=str)[:200]}")
            validated = tool.validate_params(params) if tool.param_model else params
            logger.debug(f"[_execute_tool] {tool_name} validated")

            # Global pre-interceptors
            validated = registry.run_pre_interceptors(validated, tool_name)

            # before_execute hook
            if tool.before_execute:
                validated = tool.before_execute(validated) or validated

            # 执行
            logger.debug(f"[_execute_tool] {tool_name} calling execute...")
            timeout = TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
            result = await asyncio.wait_for(tool.execute(**validated), timeout=timeout)
            logger.debug(f"[_execute_tool] {tool_name} execute returned type={type(result).__name__}")

            # after_execute hook
            if tool.after_execute:
                result = tool.after_execute(result) or result

            # Global post-interceptors
            result = registry.run_post_interceptors(result, tool_name)

            # Self-verification for destructive/modify tools
            if result.get("success") and tool.permission in ("modify", "destructive"):
                result = self._verify_tool_result(tool_name, validated, result)

            return result

        except asyncio.TimeoutError:
            timeout = TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
            logger.error(f"[ReAct] 工具 {tool_name} 执行超时（{timeout}s）")
            return {"success": False, "error": f"工具执行超时（{timeout}s）"}
        except Exception as e:
            logger.error(f"[ReAct] 工具 {tool_name} 执行异常: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _verify_tool_result(self, tool_name: str, params: Dict, result: Dict) -> Dict:
        """Post-execution self-verification for tool results."""
        import re as _re
        warnings = []

        # 1. Timestamp alignment check for cut/merge/smart_clip
        if tool_name in ("cut_video", "smart_clip"):
            start = params.get("start_time", "")
            end = params.get("end_time", "")
            if start and end:
                try:
                    s = sum(float(x) * 60 ** i for i, x in enumerate(reversed(start.split(":"))))
                    e = sum(float(x) * 60 ** i for i, x in enumerate(reversed(end.split(":"))))
                    if e <= s:
                        warnings.append(f"时间异常: 结束({end}) <= 开始({start})")
                except (ValueError, IndexError):
                    pass

        # 2. Output file existence check
        output_path = result.get("output_path") or result.get("file_path")
        if output_path:
            import os as _os
            if not _os.path.exists(output_path):
                warnings.append(f"输出文件不存在: {output_path}")

        # 3. Format completeness for known tool types
        if tool_name == "cut_video" and not result.get("output_path"):
            warnings.append("剪切结果缺少 output_path")
        if tool_name == "transcribe_video" and result.get("success") and not result.get("subtitle"):
            warnings.append("转录成功但无字幕内容")

        if warnings:
            result["_warnings"] = warnings
            logger.warning(f"[ReAct] 工具 {tool_name} 验证警告: {warnings}")
        else:
            result["_verified"] = True

        return result

    def _build_tool_summary(self, all_tool_results: List[Dict]) -> str:
        """构建工具执行摘要，存入对话历史供 LLM 后续引用"""
        if not all_tool_results:
            return ""
        lines = []
        for tr in all_tool_results:
            name = tr["name"]
            result = tr["result"]
            success = result.get("success", True)
            status = "成功" if success else "失败"
            parts = [f"- {name}: {status}"]

            # 成功时提取关键产物信息
            if success:
                if result.get("video_id"):
                    parts.append(f"video_id={result['video_id']}")
                if result.get("output_path"):
                    parts.append(f"文件={result['output_path']}")
                if result.get("filename"):
                    parts.append(f"文件名={result['filename']}")
                if result.get("duration"):
                    parts.append(f"时长={result['duration']}")
                if result.get("web_path"):
                    parts.append(f"路径={result['web_path']}")
                if result.get("videos"):
                    parts.append(f"素材数={len(result['videos'])}")
                if result.get("audio_id"):
                    parts.append(f"audio_id={result['audio_id']}")
            else:
                error = result.get("error", "")
                if error:
                    parts.append(f"错误={error[:100]}")

            lines.append(" | ".join(parts))
        return "\n".join(lines)

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
