"""
视频项目实体

用于强控制性剪辑的项目管理
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from src.domain.entities.base import Base


class VideoProject(Base):
    """视频项目实体"""
    __tablename__ = "video_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    mode = Column(String(20), default="workflow", comment="模式: workflow/conversation")
    status = Column(String(50), default="draft", comment="状态: draft/processing/completed", index=True)
    duration = Column(Float, default=0.0, comment="总时长（秒）")

    # 工作流配置
    material_ids = Column(JSON, nullable=True, comment="素材ID列表")
    creative = Column(Text, nullable=True, comment="文案内容")
    target_duration = Column(Float, nullable=True, comment="目标时长（秒）")
    style = Column(String(50), nullable=True, comment="风格")
    speaker_id = Column(Integer, ForeignKey('audio_source.id'), nullable=True, comment="音色ID")
    tts_path = Column(String(500), nullable=True, comment="TTS音频路径")
    bgm_id = Column(Integer, ForeignKey('bgm_library.id'), nullable=True, comment="BGM ID")
    bgm_volume = Column(Float, default=0.3, comment="BGM音量")
    current_step = Column(Integer, default=0, comment="当前步骤(0-3)")

    # 对话模式
    chat_history = Column(JSON, nullable=True, comment="对话历史")

    # 时间线与方案
    timeline_data = Column(JSON, nullable=True, comment="时间线数据（JSON）")
    plan_data = Column(JSON, nullable=True, comment="剪辑方案数据（JSON）")
    output_path = Column(String(500), nullable=True, comment="输出文件路径")
    output_videos = Column(JSON, nullable=True, comment="输出视频列表 [{path, created_at}]")
    proxy_dir = Column(String(500), nullable=True, comment="代理文件目录")
    subtitle_data = Column(JSON, nullable=True, comment="字幕编辑数据")
    plan_versions = Column(JSON, nullable=True, comment="版本快照列表")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    # NOTE: 时间字段使用 DateTime + datetime.utcnow，与 VideoSource/AudioSource/BGMItem 的
    # TIMESTAMP + func.current_timestamp() 不一致。统一为同一种方案需要数据迁移，暂不修改。

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "mode": self.mode or "workflow",
            "status": self.status,
            "duration": self.duration,
            "material_ids": self.material_ids or [],
            "creative": self.creative,
            "target_duration": self.target_duration,
            "style": self.style,
            "speaker_id": self.speaker_id,
            "tts_path": self.tts_path,
            "bgm_id": self.bgm_id,
            "bgm_volume": self.bgm_volume if self.bgm_volume is not None else 0.3,
            "current_step": self.current_step or 0,
            "chat_history": self.chat_history or [],
            "timeline_data": self.timeline_data,
            "plan_data": self.plan_data,
            "output_path": self.output_path,
            "output_videos": self.output_videos or [],
            "proxy_dir": self.proxy_dir,
            "subtitle_data": self.subtitle_data,
            "plan_versions": self.plan_versions or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ClipPlanItem(Base):
    """剪辑方案片段"""
    __tablename__ = "clip_plan_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('video_projects.id'), nullable=False, comment="项目 ID")
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
