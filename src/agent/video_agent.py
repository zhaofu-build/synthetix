"""
视频对话代理主模块

实现对话式视频剪辑的核心逻辑
"""
import json
import logging
from typing import Dict, List, Optional, Any
from enum import Enum
from dataclasses import dataclass, field

from src.agent.session_manager import SessionManager, SessionStatus, get_session_manager
from src.agent.intent_recognizer import IntentRecognizer, get_intent_recognizer
from src.agent.slot_filler import SlotFiller, get_slot_filler
from src.agent.tool_registry import registry
from src.agent.prompts import AgentPrompts as Prompts
from src.infrastructure.db.session import get_db_context
from src.infrastructure.repositories import VideoRepository

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """用户意图类型"""
    CUT_VIDEO = "cut_video"
    MERGE_VIDEOS = "merge_videos"
    ADD_SUBTITLE = "add_subtitle"
    ADD_AUDIO = "add_audio"
    CHANGE_SPEED = "change_speed"
    SMART_CLIP = "smart_clip"
    ANALYZE_VIDEO = "analyze_video"
    GENERATE_TTS = "generate_tts"
    LIST_VIDEOS = "list_videos"
    SEARCH_MATERIAL = "search_material"
    HELP = "help"
    CONFIRM = "confirm"
    CANCEL = "cancel"
    UNKNOWN = "unknown"


@dataclass
class DialogState:
    """对话状态（简化版，用于返回给前端）"""
    session_id: str
    status: str
    intent: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    pending_action: Optional[Dict[str, Any]] = None


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
        self.prompts = AgentPrompts()

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

        # 构建返回结果
        result["session_id"] = state.session_id
        return result

    async def _handle_idle(self, state, user_input: str) -> Dict[str, Any]:
        """处理空闲状态"""
        # 获取当前视频信息
        current_video = await self._get_current_video_name(state)

        # 意图识别
        intent_result = await self.intents.recognize(
            user_input=user_input,
            history=state.history,
            current_video=current_video
        )

        logger.info(f"意图识别结果: {intent_result.intent}, 置信度: {intent_result.confidence}")

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

        # 从用户输入中提取槽位
        new_slots = await self.slots.fill(
            user_input=user_input,
            slot_names=all_slots,
            filled_slots=state.slots
        )
        state.slots.update(new_slots)

        # 特殊处理：如果当前有视频但没指定，自动填充
        if "video_id" in required_slots and "video_id" not in state.slots:
            if state.current_video_id:
                state.slots["video_id"] = state.current_video_id

        # 检查缺失的必填槽位
        missing = self.slots.get_missing_slots(required_slots, state.slots)

        if missing:
            # 还有缺失的槽位，继续询问
            return {
                "reply": missing[0].prompt,
                "status": "collecting",
                "missing_slots": [s.name for s in missing]
            }

        # 所有必填槽位已填充，构建待执行操作
        action = await self._build_action(state)
        state.pending_action = action
        state.status = SessionStatus.CONFIRMING

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

            if result.get("success"):
                state.status = SessionStatus.COMPLETED
                reply = f"✅ {result.get('message', '操作完成')}"

                # 如果有输出文件，提供预览
                if "output_path" in result:
                    reply += f"\n\n输出文件：{result['output_path']}"
            else:
                state.status = SessionStatus.ERROR
                reply = f"❌ 执行失败：{result.get('error', '未知错误')}"

            # 重置状态，准备下一个任务
            state.reset()

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
        """执行操作"""
        tool_name = action.get("tool")
        params = action.get("params", {})

        tool = registry.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"未知工具: {tool_name}"
            }

        try:
            # 调用工具
            result = await tool.execute(**params)
            return result
        except Exception as e:
            logger.error(f"执行工具 {tool_name} 失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

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
