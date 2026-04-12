"""
对话式视频剪辑 Agent 模块

提供基于自然语言的智能视频剪辑能力
"""

from .video_agent import VideoDialogAgent, get_video_agent
from .session_manager import SessionManager, DialogState, get_session_manager
from .intent_recognizer import IntentRecognizer, get_intent_recognizer
from .slot_filler import SlotFiller, get_slot_filler
from .tool_registry import ToolRegistry, Tool, registry
from .prompts import AgentPrompts

__all__ = [
    "VideoDialogAgent",
    "DialogState",
    "get_video_agent",
    "SessionManager",
    "get_session_manager",
    "IntentRecognizer",
    "get_intent_recognizer",
    "SlotFiller",
    "get_slot_filler",
    "ToolRegistry",
    "Tool",
    "registry",
    "AgentPrompts",
]
