"""
Repository 层 - 数据访问抽象

将数据库访问逻辑从 API 层分离，提供统一的数据访问接口
"""
from src.repository.base_repository import BaseRepository, T
from src.repository.video_repository import VideoRepository
from src.repository.audio_repository import AudioRepository

__all__ = [
    'BaseRepository',
    'VideoRepository',
    'AudioRepository',
]
