"""
对话会话实体

用于持久化 Agent 对话会话状态
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON

from src.domain.entities.base import Base


class DialogSession(Base):
    """对话会话实体"""
    __tablename__ = "dialog_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), unique=True, nullable=False, index=True, comment="会话 UUID")
    status = Column(String(20), default="idle", comment="状态: idle/collecting/confirming/executing/completed/error")
    intent = Column(String(50), nullable=True, comment="当前意图")
    slots = Column(JSON, default=dict, comment="槽位数据")
    history = Column(JSON, default=list, comment="对话历史")
    current_video_id = Column(Integer, nullable=True, comment="当前视频 ID")
    pending_action = Column(JSON, nullable=True, comment="待执行操作")
    plan = Column(JSON, nullable=True, comment="剪辑方案")
    metadata_ = Column("metadata", JSON, default=dict, comment="扩展元数据")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")
