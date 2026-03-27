"""
创意内容生成服务

提供基于 LLM 的创意内容生成功能，包括关键词提取、视频剪辑等
"""
import logging
from typing import List, Dict, Any, Optional

from sqlalchemy.orm import Session

from src.application.services import (
    video_downloader_adapter as video_downloader,
    llm_adapter as use_langchain_llm,
    ffmpeg_adapter as use_ffmpeg
)
from src.shared.utils import string_util, prompt_config
from src import config
from src.infrastructure.db.session import get_db_context
from src.domain.entities.video_source import VideoSource

logger = logging.getLogger(__name__)


class CreativeService:
    """创意内容生成服务"""

    def __init__(self, db: Session = None):
        """初始化服务

        Args:
            db: 数据库会话（可选，某些方法不需要）
        """
        self.db = db

    def get_source_by_keywords(self, creative: str) -> Dict[str, Any]:
        """根据创意关键词获取视频素材

        Args:
            creative: 创意描述

        Returns:
            下载结果
        """
        logger.info("=================================llm获取搜索关键词=================================")
        keywords = self._extract_keywords(creative)
        logger.info(f"提取的关键词: {keywords}")
        logger.info("=================================下载关键词对应视频=================================")
        return video_downloader.keywords_download(keywords)

    def _extract_keywords(self, creative: str) -> List[str]:
        """从创意描述中提取关键词

        Args:
            creative: 创意描述

        Returns:
            关键词列表
        """
        keywords_prompt = prompt_config.keywords_prompt(creative)
        messages = [{"role": "user", "content": keywords_prompt}]
        keywords_resp = use_langchain_llm.generate_response(messages)
        keywords_resp = string_util.remove_think_tags(keywords_resp)
        return keywords_resp.split(",")

    def create_video_with_transitions(
        self,
        creative: str,
        audio_url: Optional[str] = None
    ) -> Dict[str, str]:
        """创建带转场的视频

        Args:
            creative: 创意描述
            audio_url: 音频URL（可选）

        Returns:
            包含最终视频路径的字典
        """
        logger.info("=================================视频处理=================================")

        # 获取视频素材信息
        source_infos = self._get_video_sources()

        # 获取音频时长（如果有）
        duration = 30
        if audio_url is not None:
            duration = self._get_audio_duration(audio_url)

        # 获取剪辑提示
        logger.info("=================================llm获取剪辑视频提示词=================================")
        clip_prompt = prompt_config.clip_prompt(creative, source_infos, duration)
        logger.info(clip_prompt)

        # 调用 LLM 生成剪辑方案
        messages = [{"role": "user", "content": clip_prompt}]
        clip_resp = use_langchain_llm.generate_response(messages)
        keywords_resp = string_util.remove_think_tags(clip_resp)

        logger.info("=================================根据llm返回视频信息进行剪辑=================================")
        logger.info(keywords_resp)

        # 解析剪辑方案
        bracket_json = string_util.get_bracket_json(keywords_resp)
        final_video = config.UPLOAD_DIR + "concatenate_videos.mp4"

        # 执行视频合成
        use_ffmpeg.concatenate_videos_with_transitions(bracket_json, final_video)

        # 合并音频（如果有）
        if audio_url is not None:
            logger.info("=================================合并文案音频=================================")
            use_ffmpeg.add_audio_to_video(final_video, audio_url, config.UPLOAD_DIR + "final_video.mp4")
            final_video = config.UPLOAD_DIR + "final_video.mp4"

        return {"concatenate_web_url": final_video}

    def _get_video_sources(self) -> List[Dict[str, Any]]:
        """获取视频素材信息

        Returns:
            视频素材信息列表
        """
        with get_db_context() as db:
            video_objs = db.query(VideoSource).filter(VideoSource.video_type == 1).all()
            return [
                {"id": obj.id, "duration": obj.duration, "description": obj.description}
                for obj in video_objs
            ]

    def _get_audio_duration(self, audio_url: str) -> float:
        """获取音频时长

        Args:
            audio_url: 音频URL

        Returns:
            音频时长（秒）

        Raises:
            ValueError: 无法获取音频信息时
        """
        video_info = use_ffmpeg.get_video_info(audio_url)
        if video_info is None:
            logger.error(f"无法获取视频信息: {audio_url}")
            raise ValueError(f"无法获取视频信息: {audio_url}")
        return video_info['duration']

    def optimize_prompt(self, prompt: str, prompt_type: str) -> str:
        """优化提示词

        Args:
            prompt: 原始提示词
            prompt_type: 提示词类型 (1:文生图, 2:图生图, 3:图生视频)

        Returns:
            优化后的提示词
        """
        logger.info("=================================调用大模型================================")
        messages = [
            {
                "role": "system",
                "content": f"现在用户正在进行{prompt_type},请你优化提示词，使生成结果更丰富，效果更好"
            },
            {"role": "user", "content": prompt}
        ]
        keywords_resp = use_langchain_llm.generate_response(messages)
        return string_util.remove_think_tags(keywords_resp)
