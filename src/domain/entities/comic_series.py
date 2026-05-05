"""
漫剧系列实体 — 管理多集漫剧和全局角色库
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON

from src.domain.entities.base import Base


class ComicSeries(Base):
    """漫剧系列"""
    __tablename__ = "comic_series"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="系列名称")
    description = Column(Text, nullable=True, comment="系列描述")
    style = Column(String(50), nullable=True, default="动漫", comment="画风")
    genre = Column(String(50), nullable=True, comment="类型")

    # 全局角色库（所有集共享）
    characters = Column(JSON, nullable=True, comment="全局角色列表")

    # 系列默认 BGM 配置
    bgm_config = Column(JSON, nullable=True, comment="默认 BGM 配置")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "style": self.style or "动漫",
            "genre": self.genre,
            "characters": self.characters or [],
            "bgm_config": self.bgm_config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
