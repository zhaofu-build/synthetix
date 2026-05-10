"""
应用配置存储实体

将用户配置覆盖持久化到数据库，替代 settings.json 文件。
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, JSON

from src.domain.entities.base import Base


class ConfigStore(Base):
    """应用配置存储表 — 键值对模式"""
    __tablename__ = 'config_store'

    id = Column(Integer, primary_key=True, autoincrement=True)
    key = Column(String(255), unique=True, nullable=False, index=True, comment="配置键 (点分隔路径)")
    value = Column(JSON, nullable=True, comment="配置值 (JSON)")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self):
        return {
            "id": self.id,
            "key": self.key,
            "value": self.value,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
