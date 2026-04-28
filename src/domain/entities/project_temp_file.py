"""项目临时文件实体"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func

from src.domain.entities.base import Base
from src.domain.entities.mixins import ToDictMixin


class ProjectTempFile(Base, ToDictMixin):
    """项目临时文件表 — 存放聊天上传和工具产出的临时文件"""
    __tablename__ = 'project_temp_file'

    id = Column(Integer, primary_key=True, autoincrement=True)
    project_id = Column(Integer, ForeignKey('video_projects.id'), nullable=False, index=True)
    session_id = Column(String(64), nullable=True, index=True)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    web_path = Column(String(500), nullable=False)
    file_type = Column(String(20), default='video')
    file_size = Column(Integer, default=0)
    source = Column(String(50), default='upload')
    created_at = Column(DateTime, default=func.current_timestamp())

    def __repr__(self):
        return f"<ProjectTempFile(id={self.id}, project_id={self.project_id}, file_name='{self.file_name}')>"
