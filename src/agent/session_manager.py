"""
会话管理模块

管理用户对话会话的状态和生命周期
"""
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum


class SessionStatus(Enum):
    """会话状态"""
    IDLE = "idle"                    # 空闲，等待用户输入
    COLLECTING = "collecting"        # 收集信息
    CONFIRMING = "confirming"        # 确认方案
    EXECUTING = "executing"          # 执行中
    COMPLETED = "completed"          # 完成
    ERROR = "error"                  # 错误


@dataclass
class DialogState:
    """对话状态"""
    session_id: str
    status: SessionStatus = SessionStatus.IDLE
    intent: Optional[str] = None
    slots: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict[str, str]] = field(default_factory=list)
    current_video_id: Optional[int] = None
    pending_action: Optional[Dict[str, Any]] = None
    plan: Optional[Dict[str, Any]] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str):
        """添加消息到历史（带截断保护）"""
        self.history.append({"role": role, "content": content})
        # 超过上限时截断，保留最近的消息
        from src.shared.constants import AgentConfig
        if len(self.history) > AgentConfig.MAX_HISTORY_MESSAGES:
            self.history = self.history[-AgentConfig.HISTORY_TRUNCATE_KEEP:]
        self.updated_at = time.time()

    def get_last_user_message(self) -> Optional[str]:
        """获取最后一条用户消息"""
        for msg in reversed(self.history):
            if msg["role"] == "user":
                return msg["content"]
        return None

    def get_context_messages(self, limit: int = 5) -> List[Dict[str, str]]:
        """获取上下文消息（用于 LLM）"""
        return self.history[-limit:] if self.history else []

    def reset(self):
        """重置状态（保留会话 ID 和历史）"""
        self.status = SessionStatus.IDLE
        self.intent = None
        self.slots = {}
        self.pending_action = None
        self.plan = None
        self.updated_at = time.time()


class SessionManager:
    """会话管理器"""

    def __init__(self, session_timeout: int = 3600):
        """
        初始化会话管理器

        Args:
            session_timeout: 会话超时时间（秒），默认 1 小时
        """
        self._sessions: Dict[str, DialogState] = {}
        self._session_timeout = session_timeout

    def create_session(self, session_id: Optional[str] = None) -> DialogState:
        """
        创建新会话

        Args:
            session_id: 可选的会话 ID，不提供则自动生成

        Returns:
            DialogState: 新创建的会话状态
        """
        sid = session_id or str(uuid.uuid4())
        state = DialogState(session_id=sid)
        self._sessions[sid] = state
        return state

    def get_session(self, session_id: str) -> Optional[DialogState]:
        """
        获取会话

        Args:
            session_id: 会话 ID

        Returns:
            DialogState: 会话状态，不存在则返回 None
        """
        session = self._sessions.get(session_id)
        if session:
            session.updated_at = time.time()
        return session

    def get_or_create_session(self, session_id: Optional[str] = None) -> DialogState:
        """
        获取或创建会话

        Args:
            session_id: 会话 ID，不提供则创建新会话

        Returns:
            DialogState: 会话状态
        """
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        return self.create_session(session_id)

    def delete_session(self, session_id: str) -> bool:
        """
        删除会话

        Args:
            session_id: 会话 ID

        Returns:
            bool: 是否删除成功
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话

        Returns:
            int: 清理的会话数量
        """
        current_time = time.time()
        expired = [
            sid for sid, state in self._sessions.items()
            if current_time - state.updated_at > self._session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]
        return len(expired)

    def get_active_sessions(self) -> List[DialogState]:
        """
        获取所有活跃会话

        Returns:
            List[DialogState]: 活跃会话列表
        """
        return list(self._sessions.values())

    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self._sessions)


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
