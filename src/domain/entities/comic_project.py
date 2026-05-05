"""
漫剧项目实体
"""
from datetime import datetime
from typing import Dict, Any
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, JSON, ForeignKey

from src.domain.entities.base import Base


class ComicProject(Base):
    """漫剧项目实体"""
    __tablename__ = "comic_projects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False, comment="项目名称")
    description = Column(Text, nullable=True, comment="项目描述")
    genre = Column(String(50), nullable=True, comment="类型: drama/comedy/action/romance/horror")
    style = Column(String(50), nullable=True, default="动漫", comment="画风: 动漫/写实/水墨/像素/美漫")
    status = Column(String(50), default="draft", comment="状态: draft/scripting/generating/compositing/completed")

    # 系列关联（多集支持）
    series_id = Column(Integer, ForeignKey("comic_series.id"), nullable=True, comment="所属系列 ID")
    episode_number = Column(Integer, default=1, comment="集数序号")
    target_duration = Column(Float, nullable=True, comment="目标时长（秒）")

    # 脚本结构（JSON 存储）
    script_data = Column(JSON, nullable=True, comment="完整脚本 JSON")
    characters = Column(JSON, nullable=True, comment="角色定义列表")
    panels = Column(JSON, nullable=True, comment="分镜列表（含图片/音频路径）")

    # 音频配置
    audio_config = Column(JSON, nullable=True, comment="音频配置")
    bgm_config = Column(JSON, nullable=True, comment="BGM 配置 {path, volume, fade_in, fade_out}")

    # 工作流步骤 (0=脚本, 1=角色, 2=分镜, 3=音频, 4=BGM, 5=合成)
    current_step = Column(Integer, default=0, comment="当前工作流步骤")

    # 输出
    output_videos = Column(JSON, nullable=True, comment="输出视频列表 [{path, created_at}]")

    created_at = Column(DateTime, default=datetime.utcnow, comment="创建时间")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment="更新时间")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "genre": self.genre,
            "style": self.style or "动漫",
            "status": self.status or "draft",
            "series_id": self.series_id,
            "episode_number": self.episode_number or 1,
            "target_duration": self.target_duration,
            "script_data": self.script_data,
            "characters": self.characters or [],
            "panels": self.panels or [],
            "audio_config": self.audio_config or {},
            "bgm_config": self.bgm_config or {},
            "current_step": self.current_step or 0,
            "output_videos": self.output_videos or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
