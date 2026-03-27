"""
视频素材 Repository

提供视频素材相关的数据访问操作
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from src.infrastructure.repositories.base_repository import BaseRepository
from src.domain.entities.video_source import VideoSource

logger = logging.getLogger(__name__)


class VideoRepository(BaseRepository[VideoSource]):
    """视频素材 Repository"""

    def __init__(self, session: Session):
        """
        初始化 VideoRepository

        Args:
            session: 数据库会话
        """
        super().__init__(session, VideoSource)

    def get_by_type(self, video_type: int, skip: int = 0, limit: int = 100) -> List[VideoSource]:
        """
        根据视频类型获取视频列表

        Args:
            video_type: 视频类型
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            视频实体列表
        """
        return self._session.query(VideoSource).filter(
            VideoSource.video_type == video_type
        ).offset(skip).limit(limit).all()

    def get_active_videos(
        self,
        video_type: Optional[int] = None,
        skip: int = 0,
        limit: int = 100
    ) -> List[VideoSource]:
        """
        获取未删除的视频列表

        Args:
            video_type: 可选的视频类型过滤
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            视频实体列表
        """
        query = self._session.query(VideoSource).filter(VideoSource.del_flag == 0)

        if video_type is not None:
            query = query.filter(VideoSource.video_type == video_type)

        return query.offset(skip).limit(limit).all()

    def count_by_type(self, video_type: int) -> int:
        """
        统计指定类型的视频数量

        Args:
            video_type: 视频类型

        Returns:
            视频数量
        """
        return self._session.query(func.count(VideoSource.id)).filter(
            VideoSource.video_type == video_type
        ).scalar() or 0

    def count_active(self, video_type: Optional[int] = None) -> int:
        """
        统计未删除的视频数量

        Args:
            video_type: 可选的视频类型过滤

        Returns:
            视频数量
        """
        query = self._session.query(func.count(VideoSource.id)).filter(
            VideoSource.del_flag == 0
        )

        if video_type is not None:
            query = query.filter(VideoSource.video_type == video_type)

        return query.scalar() or 0

    def get_by_name(self, name: str) -> Optional[VideoSource]:
        """
        根据视频名称查询视频

        Args:
            name: 视频名称

        Returns:
            视频实体，不存在则返回 None
        """
        return self._session.query(VideoSource).filter(
            VideoSource.video_name == name
        ).first()

    def get_random_active(self, video_type: Optional[int] = None) -> Optional[VideoSource]:
        """
        随机获取一个未删除的视频

        Args:
            video_type: 可选的视频类型过滤

        Returns:
            随机视频实体，不存在则返回 None
        """
        query = self._session.query(VideoSource).filter(VideoSource.del_flag == 0)

        if video_type is not None:
            query = query.filter(VideoSource.video_type == video_type)

        return query.order_by(func.random()).limit(1).first()

    def update_description(self, video_id: int, description: str) -> Optional[VideoSource]:
        """
        更新视频描述

        Args:
            video_id: 视频 ID
            description: 新的描述内容

        Returns:
            更新后的视频实体，不存在则返回 None
        """
        return self.update(video_id, description=description)

    def mark_as_used(self, video_id: int) -> Optional[VideoSource]:
        """
        标记视频为使用中

        Args:
            video_id: 视频 ID

        Returns:
            更新后的视频实体，不存在则返回 None
        """
        return self.update(video_id, video_type=1)

    def mark_as_unused(self, video_id: int) -> Optional[VideoSource]:
        """
        标记视频为未使用

        Args:
            video_id: 视频 ID

        Returns:
            更新后的视频实体，不存在则返回 None
        """
        return self.update(video_id, video_type=0)

    def to_dict(self, video: VideoSource) -> Dict[str, Any]:
        """
        将视频实体转换为字典

        Args:
            video: 视频实体

        Returns:
            视频信息字典
        """
        return {
            "id": video.id,
            "video_name": video.video_name,
            "web_path": video.web_path,
            "local_path": video.local_path,
            "duration": video.duration,
            "duration_hms": video.duration_hms,
            "description": video.description,
            "video_type": video.video_type,
            "create_time": video.create_time,
            "del_flag": video.del_flag,
        }

    def bulk_to_dict(self, videos: List[VideoSource]) -> List[Dict[str, Any]]:
        """
        批量将视频实体转换为字典

        Args:
            videos: 视频实体列表

        Returns:
            视频信息字典列表
        """
        return [self.to_dict(v) for v in videos]

    def get_by_id_dict(self, video_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取视频字典

        Args:
            video_id: 视频 ID

        Returns:
            视频信息字典，不存在则返回 None
        """
        video = self.get_by_id(video_id)
        return self.to_dict(video) if video else None
