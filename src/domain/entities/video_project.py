"""
视频项目实体

用于强控制性剪辑的项目管理
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON
from sqlalchemy.orm import relationship

from src.domain.entities.base import Base


class VideoProject(Base):
    """视频项目实体"""
    __tablename__ = "video_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    status = Column(String(50), default="draft", comment="状态: draft/processing/completed")
    duration = Column(Float, default=0.0, comment="总时长（秒）")
    timeline_data = Column(JSON, nullable=True, comment="时间线数据（JSON）")
    plan_data = Column(JSON, nullable=True, comment="剪辑方案数据（JSON）")
    output_path = Column(String(500), nullable=True, comment="输出文件路径")
    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "duration": self.duration,
            "timeline_data": self.timeline_data,
            "plan_data": self.plan_data,
            "output_path": self.output_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ClipPlanItem(Base):
    """剪辑方案片段"""
    __tablename__ = "clip_plan_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, nullable=False, comment="项目 ID")
    sequence = Column(Integer, default=0, comment="顺序")
    material_id = Column(Integer, nullable=True, comment="素材 ID")
    material_name = Column(String(255), nullable=True, comment="素材名称")
    start_time = Column(String(20), default="00:00:00", comment="素材开始时间")
    end_time = Column(String(20), nullable=True, comment="素材结束时间")
    duration = Column(Float, default=0.0, comment="片段时长")
    purpose = Column(Text, nullable=True, comment="用途说明")
    transition_type = Column(String(50), default="cut", comment="转场类型")
    transition_duration = Column(Float, default=0.5, comment="转场时长")
    created_at = Column(DateTime, default=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "sequence": self.sequence,
            "material_id": self.material_id,
            "material_name": self.material_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "purpose": self.purpose,
            "transition_type": self.transition_type,
            "transition_duration": self.transition_duration,
        }
