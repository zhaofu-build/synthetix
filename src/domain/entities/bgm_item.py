"""
BGM 素材实体
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, TIMESTAMP, func

from src.domain.entities.base import Base


class BGMItem(Base):
    """BGM 素材表"""
    __tablename__ = "bgm_library"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="BGM名称")
    web_path = Column(Text, nullable=True, comment="Web访问路径")
    local_path = Column(Text, nullable=True, comment="本地存储路径")
    style = Column(String(100), nullable=True, comment="风格标签")
    duration = Column(Float, nullable=True, comment="时长(秒)")
    description = Column(Text, nullable=True, comment="描述")
    created_at = Column(TIMESTAMP, default=func.current_timestamp(), comment="创建时间")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "web_path": self.web_path,
            "local_path": self.local_path,
            "style": self.style,
            "duration": self.duration,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
