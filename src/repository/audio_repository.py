"""
音频素材 Repository

提供音频素材相关的数据访问操作
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from src.repository.base_repository import BaseRepository
from src.model.entity.audio_source import AudioSource

logger = logging.getLogger(__name__)


class AudioRepository(BaseRepository[AudioSource]):
    """音频素材 Repository"""

    def __init__(self, session: Session):
        """
        初始化 AudioRepository

        Args:
            session: 数据库会话
        """
        super().__init__(session, AudioSource)

    def get_active_audios(self, skip: int = 0, limit: int = 100) -> List[AudioSource]:
        """
        获取未删除的音频列表

        Args:
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            音频实体列表
        """
        return self._session.query(AudioSource).filter(
            AudioSource.del_flag == 0
        ).offset(skip).limit(limit).all()

    def count_active(self) -> int:
        """
        统计未删除的音频数量

        Returns:
            音频数量
        """
        return self._session.query(func.count(AudioSource.id)).filter(
            AudioSource.del_flag == 0
        ).scalar() or 0

    def get_by_name(self, name: str) -> Optional[AudioSource]:
        """
        根据音频名称查询音频

        Args:
            name: 音频名称

        Returns:
            音频实体，不存在则返回 None
        """
        return self._session.query(AudioSource).filter(
            AudioSource.audio_name == name
        ).first()

    def get_random_active(self) -> Optional[AudioSource]:
        """
        随机获取一个未删除的音频

        Returns:
            随机音频实体，不存在则返回 None
        """
        return self._session.query(AudioSource).filter(
            AudioSource.del_flag == 0
        ).order_by(func.random()).limit(1).first()

    def search_by_name(self, name_pattern: str, skip: int = 0, limit: int = 100) -> List[AudioSource]:
        """
        根据音频名称模糊搜索

        Args:
            name_pattern: 名称模糊匹配模式
            skip: 跳过的记录数
            limit: 返回的最大记录数

        Returns:
            音频实体列表
        """
        return self._session.query(AudioSource).filter(
            AudioSource.audio_name.like(f"%{name_pattern}%")
        ).offset(skip).limit(limit).all()

    def get_by_seed(self, seed: int) -> Optional[AudioSource]:
        """
        根据种子值查询音频

        Args:
            seed: 随机种子值

        Returns:
            音频实体，不存在则返回 None
        """
        return self._session.query(AudioSource).filter(
            AudioSource.seed == seed
        ).first()

    def to_dict(self, audio: AudioSource, include_web_path: bool = False) -> Dict[str, Any]:
        """
        将音频实体转换为字典

        Args:
            audio: 音频实体
            include_web_path: 是否包含完整 web 路径

        Returns:
            音频信息字典
        """
        result = {
            "id": audio.id,
            "audio_name": audio.audio_name,
            "prompt_text": audio.prompt_text,
            "web_path": audio.web_path,
            "seed": audio.seed,
            "speed": audio.speed,
            "top_p": audio.top_p,
            "temperature": audio.temperature,
            "repetition_penalty": audio.repetition_penalty,
            "create_time": audio.create_time,
        }

        if include_web_path:
            import os
            import config
            result["web_path"] = os.path.join(config.source_audios_dir, audio.web_path)

        return result

    def bulk_to_dict(self, audios: List[AudioSource], include_web_path: bool = False) -> List[Dict[str, Any]]:
        """
        批量将音频实体转换为字典

        Args:
            audios: 音频实体列表
            include_web_path: 是否包含完整 web 路径

        Returns:
            音频信息字典列表
        """
        return [self.to_dict(a, include_web_path) for a in audios]

    def get_by_id_dict(self, audio_id: int, include_web_path: bool = False) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取音频字典

        Args:
            audio_id: 音频 ID
            include_web_path: 是否包含完整 web 路径

        Returns:
            音频信息字典，不存在则返回 None
        """
        audio = self.get_by_id(audio_id)
        return self.to_dict(audio, include_web_path) if audio else None
