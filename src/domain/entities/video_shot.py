"""
视频镜头实体

存储视频分割后的镜头级元数据，用于结构化索引和快速检索。
每个镜头代表视频中一个连续片段（由场景切换点分割）。
"""
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import Column, Integer, Float, String, Text, DateTime, JSON, ForeignKey, Index

from src.domain.entities.base import Base


class VideoShot(Base):
    """视频镜头表"""
    __tablename__ = 'video_shots'

    id = Column(Integer, primary_key=True, autoincrement=True)
    video_id = Column(Integer, ForeignKey('video_source.id'), nullable=False, index=True)
    shot_index = Column(Integer, default=0, comment="镜头序号（从 0 开始）")
    scene_group = Column(Integer, default=0, comment="场景组号")

    start_time = Column(Float, default=0.0, comment="镜头开始时间（秒）")
    end_time = Column(Float, default=0.0, comment="镜头结束时间（秒）")

    keyframe_paths = Column(JSON, default=list, comment="关键帧路径列表 [{path, timestamp}]")
    subtitle_text = Column(Text, nullable=True, comment="该时段的字幕文本")
    description = Column(Text, nullable=True, comment="镜头描述（来自关键帧 VL 分析）")

    index_status = Column(
        String(20), default="pending",
        comment="索引状态: pending/processing/complete/failed"
    )

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index('ix_video_shots_video_id_status', 'video_id', 'index_status'),
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "video_id": self.video_id,
            "shot_index": self.shot_index,
            "scene_group": self.scene_group,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.end_time - self.start_time, 2) if self.end_time and self.start_time else 0,
            "keyframe_paths": self.keyframe_paths or [],
            "subtitle_text": self.subtitle_text,
            "description": self.description,
            "index_status": self.index_status,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
