"""
会话管理模块

管理用户对话会话的状态和生命周期，支持内存缓存 + 数据库持久化
"""
import json
import uuid
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


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
    project_id: Optional[int] = None
    last_video_list: List[Dict] = field(default_factory=list)
    last_referenced_video_id: Optional[int] = None

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
    """会话管理器（内存缓存 + 数据库持久化）"""

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
        self._persist_session(state)
        return state

    def get_session(self, session_id: str) -> Optional[DialogState]:
        """
        获取会话（先查内存，再查数据库）

        Args:
            session_id: 会话 ID

        Returns:
            DialogState: 会话状态，不存在则返回 None
        """
        session = self._sessions.get(session_id)
        if session:
            session.updated_at = time.time()
            return session

        # 内存未命中，从数据库加载
        session = self._load_from_db(session_id)
        if session:
            self._sessions[session_id] = session
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
        self._delete_from_db(session_id)
        return True

    def cleanup_expired_sessions(self) -> int:
        """
        清理过期会话（内存 + 数据库）

        Returns:
            int: 清理的会话数量
        """
        # 清理内存
        current_time = time.time()
        expired = [
            sid for sid, state in self._sessions.items()
            if current_time - state.updated_at > self._session_timeout
        ]
        for sid in expired:
            del self._sessions[sid]

        # 清理数据库
        db_cleaned = self._cleanup_db_expired()

        total = len(expired) + db_cleaned
        if total > 0:
            logger.info(f"清理了 {len(expired)} 个内存会话, {db_cleaned} 个数据库会话")
        return total

    def get_active_sessions(self) -> List[DialogState]:
        """
        获取所有活跃会话

        Returns:
            List[DialogState]: 活跃会话列表
        """
        return list(self._sessions.values())

    def get_sessions_by_project(self, project_id: int) -> List[DialogState]:
        """获取指定项目的所有会话（内存 + 数据库）"""
        results = [s for s in self._sessions.values() if s.project_id == project_id]
        if results:
            return results
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.dialog_session import DialogSession
            with get_db_context() as db:
                rows = db.query(DialogSession).filter(
                    DialogSession.metadata_["project_id"].as_integer() == project_id
                ).order_by(DialogSession.updated_at.desc()).limit(20).all()
                for row in rows:
                    if row.session_id not in self._sessions:
                        state = self._load_from_db(row.session_id)
                        if state:
                            self._sessions[row.session_id] = state
                            results.append(state)
        except Exception as e:
            logger.warning(f"按项目查询会话失败: {e}")
        return results

    def restore_last_session(self, project_id: int) -> Optional[DialogState]:
        """恢复项目最近一次会话"""
        sessions = self.get_sessions_by_project(project_id)
        if not sessions:
            return None
        sessions.sort(key=lambda s: s.updated_at, reverse=True)
        return sessions[0]

    def get_session_count(self) -> int:
        """获取会话数量"""
        return len(self._sessions)

    def persist_session(self, state: DialogState):
        """外部调用的持久化接口"""
        self._persist_session(state)

    # ==================== 数据库持久化 ====================

    def _persist_session(self, state: DialogState):
        """将会话状态持久化到数据库"""
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.dialog_session import DialogSession

            with get_db_context(commit=True) as db:
                existing = db.query(DialogSession).filter_by(
                    session_id=state.session_id
                ).first()

                if existing:
                    existing.status = state.status.value if isinstance(state.status, SessionStatus) else state.status
                    existing.intent = state.intent
                    existing.slots = state.slots
                    existing.history = state.history
                    existing.current_video_id = state.current_video_id
                    existing.pending_action = state.pending_action
                    existing.plan = state.plan
                    existing.metadata_ = state.metadata
                    existing.updated_at = datetime.utcnow()
                else:
                    row = DialogSession(
                        session_id=state.session_id,
                        status=state.status.value if isinstance(state.status, SessionStatus) else state.status,
                        intent=state.intent,
                        slots=state.slots,
                        history=state.history,
                        current_video_id=state.current_video_id,
                        pending_action=state.pending_action,
                        plan=state.plan,
                        metadata_=state.metadata,
                    )
                    db.add(row)
        except Exception as e:
            logger.warning(f"会话持久化失败: {e}")

    def _load_from_db(self, session_id: str) -> Optional[DialogState]:
        """从数据库加载会话"""
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.dialog_session import DialogSession

            with get_db_context() as db:
                row = db.query(DialogSession).filter_by(session_id=session_id).first()
                if not row:
                    return None

                state = DialogState(
                    session_id=row.session_id,
                    status=SessionStatus(row.status),
                    intent=row.intent,
                    slots=row.slots or {},
                    history=row.history or [],
                    current_video_id=row.current_video_id,
                    pending_action=row.pending_action,
                    plan=row.plan,
                    created_at=row.created_at.timestamp() if row.created_at else time.time(),
                    updated_at=row.updated_at.timestamp() if row.updated_at else time.time(),
                    metadata=row.metadata_ or {},
                )
                return state
        except Exception as e:
            logger.warning(f"从数据库加载会话失败: {e}")
            return None

    def _delete_from_db(self, session_id: str):
        """从数据库删除会话"""
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.dialog_session import DialogSession

            with get_db_context(commit=True) as db:
                db.query(DialogSession).filter_by(session_id=session_id).delete()
        except Exception as e:
            logger.warning(f"从数据库删除会话失败: {e}")

    def _cleanup_db_expired(self) -> int:
        """清理数据库中的过期会话"""
        try:
            from src.infrastructure.db.session import get_db_context
            from src.domain.entities.dialog_session import DialogSession
            from src.shared.constants import AgentConfig
            from datetime import datetime, timedelta

            cutoff = datetime.utcnow() - timedelta(seconds=AgentConfig.SESSION_DB_TTL)

            with get_db_context(commit=True) as db:
                count = db.query(DialogSession).filter(
                    DialogSession.updated_at < cutoff
                ).delete()
                return count
        except Exception as e:
            logger.warning(f"数据库过期会话清理失败: {e}")
            return 0


# 全局会话管理器实例
_session_manager: Optional[SessionManager] = None


def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager
