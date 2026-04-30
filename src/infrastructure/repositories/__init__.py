"""
Repository 层 - 数据访问抽象

将数据库访问逻辑从 API 层分离，提供统一的数据访问接口
"""
from src.infrastructure.repositories.base_repository import BaseRepository, T
from src.infrastructure.repositories.video_repository import VideoRepository
from src.infrastructure.repositories.audio_repository import AudioRepository
from src.infrastructure.repositories.shot_repository import ShotRepository

__all__ = [
    'BaseRepository',
    'VideoRepository',
    'AudioRepository',
    'ShotRepository',
]
