"""
视频镜头 Repository
"""
from typing import List

from sqlalchemy.orm import Session
from sqlalchemy import func

from src.infrastructure.repositories.base_repository import BaseRepository
from src.domain.entities.video_shot import VideoShot


class ShotRepository(BaseRepository[VideoShot]):
    """视频镜头 Repository"""

    def __init__(self, session: Session):
        super().__init__(session, VideoShot)

    def get_by_video_id(self, video_id: int) -> List[VideoShot]:
        return (self._session.query(VideoShot)
                .filter(VideoShot.video_id == video_id)
                .order_by(VideoShot.shot_index)
                .all())

    def get_complete_shots(self, video_id: int) -> List[VideoShot]:
        return (self._session.query(VideoShot)
                .filter(VideoShot.video_id == video_id,
                        VideoShot.index_status == "complete")
                .order_by(VideoShot.shot_index)
                .all())

    def has_complete_index(self, video_id: int) -> bool:
        total = self._session.query(func.count(VideoShot.id)).filter(
            VideoShot.video_id == video_id
        ).scalar() or 0
        if total == 0:
            return False
        complete = self._session.query(func.count(VideoShot.id)).filter(
            VideoShot.video_id == video_id,
            VideoShot.index_status == "complete"
        ).scalar() or 0
        return complete == total

    def delete_by_video_id(self, video_id: int) -> int:
        count = self._session.query(VideoShot).filter(
            VideoShot.video_id == video_id
        ).delete()
        self._session.flush()
        return count
