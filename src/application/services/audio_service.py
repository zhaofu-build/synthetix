"""
音频服务层

封装音频相关的业务逻辑，包括音色保存、TTS、音频处理等
"""
import os
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

import soundfile as sf
from src import config
from src.application.services import (
    dh_live_adapter as dh_live,
    fish_speech_adapter as fish_voice
)
from src.shared.utils import string_util, file_util
from src.infrastructure.repositories import AudioRepository

logger = logging.getLogger(__name__)


class AudioService:
    """音频服务类"""

    def __init__(self, db: Session):
        """
        初始化音频服务

        Args:
            db: 数据库会话
        """
        self.db = db
        self._repository = AudioRepository(db)

    def save_timbre(
        self,
        file_stream,
        audio_name: str,
        prompt_text: str,
        seed: int,
        speed: float,
        top_p: float,
        temperature: float,
        repetition_penalty: float,
        output_format: str = "wav",
        upload_dir: str = None
    ) -> Dict[str, Any]:
        """
        保存音色文件到数据库

        Args:
            file_stream: 上传的文件流
            audio_name: 音色名称
            prompt_text: 参考文本
            seed: 随机种子
            speed: 语速因子
            top_p: 采样概率阈值
            temperature: 温度参数
            repetition_penalty: 重复惩罚因子
            output_format: 输出格式
            upload_dir: 上传目录

        Returns:
            包含音色 ID 的字典
        """
        if upload_dir is None:
            upload_dir = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir)

        # 确保目录存在
        os.makedirs(upload_dir, exist_ok=True)

        # 生成文件名
        filename = f"{uuid.uuid4().hex}.{output_format}"
        file_path = os.path.join(upload_dir, filename)

        # 分块写入文件
        chunk_size = 1024 * 1024
        try:
            with open(file_path, "wb") as buffer:
                while True:
                    if hasattr(file_stream, 'read'):
                        content = file_stream.read(chunk_size)
                        if not content:
                            break
                        buffer.write(content)
                    else:
                        break
        except Exception as e:
            logger.error(f"文件写入失败: {e}")
            raise IOError(f"文件写入失败: {e}")

        # 保存到数据库
        audio_obj = self._repository.create(
            audio_name=audio_name,
            prompt_text=prompt_text,
            web_path=filename,
            seed=seed,
            speed=speed,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
        )

        logger.info(f"音色保存成功: ID={audio_obj.id}, 名称={audio_name}")
        return {
            "id": audio_obj.id,
            "filename": filename,
            "audio_name": audio_name
        }

    def save_timbre_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        audio_name: str,
        prompt_text: str,
        seed: int,
        speed: float,
        top_p: float,
        temperature: float,
        repetition_penalty: float,
        output_format: str = "wav",
        upload_dir: str = None
    ) -> Dict[str, Any]:
        """
        从字节数据保存音色文件到数据库

        Args:
            file_content: 文件内容（字节）
            filename: 原始文件名
            audio_name: 音色名称
            prompt_text: 参考文本
            seed: 随机种子
            speed: 语速因子
            top_p: 采样概率阈值
            temperature: 温度参数
            repetition_penalty: 重复惩罚因子
            output_format: 输出格式
            upload_dir: 上传目录

        Returns:
            包含音色 ID 的字典
        """
        if upload_dir is None:
            upload_dir = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir)

        # 确保目录存在
        os.makedirs(upload_dir, exist_ok=True)

        # 生成文件名
        save_filename = f"{uuid.uuid4().hex}.{output_format}"
        file_path = os.path.join(upload_dir, save_filename)

        # 写入文件
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            logger.error(f"文件写入失败: {e}")
            raise IOError(f"文件写入失败: {e}")

        # 保存到数据库
        audio_obj = self._repository.create(
            audio_name=audio_name,
            prompt_text=prompt_text,
            web_path=save_filename,
            seed=seed,
            speed=speed,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            del_flag=0,  # 明确设置未删除标志
        )

        logger.info(f"音色保存成功: ID={audio_obj.id}, 名称={audio_name}, 原文件名={filename}")
        return {
            "id": audio_obj.id,
            "filename": save_filename,
            "audio_name": audio_name
        }

    def generate_fish_speech_tts(
        self,
        text: str,
        audio_source_id: int = -1,
        seed: int = 42,
        speed_factor: float = 1.0,
        top_p: float = 0.5,
        temperature: float = 0.5,
        repetition_penalty: float = 1.35,
        references_audio: Optional[str] = None,
        references_text: str = "",
        output_format: str = "wav",
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        生成语音（Fish Speech TTS）

        Args:
            text: 要合成的文本
            audio_source_id: 音色ID，-1表示使用自定义参考音频
            seed: 随机种子
            speed_factor: 语速因子
            top_p: 采样概率阈值
            temperature: 温度参数
            repetition_penalty: 重复惩罚因子
            references_audio: 参考音频(base64编码)
            references_text: 参考音频文本
            output_format: 输出格式
            output_dir: 输出目录

        Returns:
            包含生成文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        references = []

        if audio_source_id == -1:
            # 使用自定义参考音频
            if references_audio is not None:
                references = [{
                    "audio": references_audio,
                    "text": references_text
                }]
            audio_data = fish_voice.fish_voice(
                text, output_format, references, seed,
                speed_factor, top_p,
                temperature, repetition_penalty
            )
        else:
            # 使用数据库中的音色
            audio_obj = self._repository.get_by_id(audio_source_id)
            if not audio_obj:
                raise ValueError(f"音色 ID {audio_source_id} 不存在")

            web_path = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir, audio_obj.web_path)
            references = [{
                "audio": file_util.audio_to_base64(web_path),
                "text": audio_obj.prompt_text
            }]
            audio_data = fish_voice.fish_voice(
                text, output_format, references, audio_obj.seed,
                audio_obj.speed, audio_obj.top_p,
                audio_obj.temperature, audio_obj.repetition_penalty
            )

        # 保存音频文件
        filename = f"{uuid.uuid4().hex}.{output_format}"
        file_path = os.path.join(output_dir, filename)

        with open(file_path, "wb") as f:
            f.write(audio_data)

        logger.info(f"语音生成成功: 文件名={filename}")
        return {
            "filename": filename,
            "web_path": config.UPLOAD_DIR + filename,
            "local_path": file_path
        }

    def separate_audio(
        self,
        audio_path: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        分离音频和伴奏

        Args:
            audio_path: 音频文件路径
            output_dir: 输出目录

        Returns:
            包含人声和伴奏路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        try:
            vocal_url, accompaniment_url = dh_live.do_s(audio_path, output_dir)
            logger.info(f"音频分离成功")
            return {
                "vocal_path": output_dir + vocal_url,
                "vocal_web_path": output_dir + vocal_url,
                "accompaniment_path": output_dir + accompaniment_url,
                "accompaniment_web_path": output_dir + accompaniment_url
            }
        except Exception as e:
            logger.error(f"音频分离失败: {e}")
            raise ValueError(f"音频分离失败: {e}")

    def merge_audio(
        self,
        source_audio_path: str,
        accompaniment_url: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        合并人声和伴奏

        Args:
            source_audio_path: 人声文件路径
            accompaniment_url: 伴奏文件路径
            output_dir: 输出目录

        Returns:
            包含合并后文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        try:
            final_url = dh_live.do_m(source_audio_path, accompaniment_url, output_dir)
            logger.info(f"音频合并成功")
            return {
                "merged_path": output_dir + final_url,
                "merged_web_path": output_dir + final_url
            }
        except Exception as e:
            logger.error(f"音频合并失败: {e}")
            raise ValueError(f"音频合并失败: {e}")

    def delete_audio(self, audio_id: int) -> bool:
        """
        删除音色（包括文件和数据库记录）

        Args:
            audio_id: 音色 ID

        Returns:
            删除成功返回 True

        Raises:
            FileNotFoundError: 音色不存在
        """
        audio_obj = self._repository.get_by_id(audio_id)
        if not audio_obj:
            raise FileNotFoundError(f"音色 {audio_id} 不存在")

        # 删除文件
        web_path = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir, audio_obj.web_path)
        file_util.del_file(web_path)

        # 删除数据库记录
        self._repository.delete(audio_id)
        logger.info(f"音色已删除: ID={audio_id}")
        return True

    def get_paginated_audios(
        self,
        page: int = 1,
        page_size: int = 10
    ) -> Dict[str, Any]:
        """
        获取分页音色列表

        Args:
            page: 页码
            page_size: 每页大小

        Returns:
            包含 items, total, page, page_size, total_pages 的字典
        """
        total = self._repository.count_active()
        skip = (page - 1) * page_size
        items = self._repository.get_active_audios(skip=skip, limit=page_size)

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": self._repository.bulk_to_dict(items, include_web_path=True),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def get_timbre_for_tts(self, audio_id: int) -> Dict[str, Any]:
        """
        获取音色信息用于 TTS

        Args:
            audio_id: 音色 ID

        Returns:
            包含音色信息的字典
        """
        audio_obj = self._repository.get_by_id(audio_id)
        if not audio_obj:
            raise ValueError(f"音色 {audio_id} 不存在")

        web_path = os.path.join(config.ROOT_DIR_WIN, config.source_audios_dir, audio_obj.web_path)

        return {
            "id": audio_obj.id,
            "audio_name": audio_obj.audio_name,
            "prompt_text": audio_obj.prompt_text,
            "web_path": web_path,
            "seed": audio_obj.seed,
            "speed": audio_obj.speed,
            "top_p": audio_obj.top_p,
            "temperature": audio_obj.temperature,
            "repetition_penalty": audio_obj.repetition_penalty,
        }

    def update_audio(self, audio_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """
        更新音色信息

        Args:
            audio_id: 音色 ID
            **kwargs: 要更新的字段（audio_name, prompt_text, seed, speed, top_p, temperature, repetition_penalty）

        Returns:
            更新后的音色信息字典，不存在则返回 None
        """
        audio_obj = self._repository.update(audio_id, **kwargs)
        if not audio_obj:
            return None
        return audio_obj.to_dict()

    def get_audio_by_id(self, audio_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取音色信息

        Args:
            audio_id: 音色 ID

        Returns:
            音色信息字典，不存在则返回 None
        """
        audio_obj = self._repository.get_by_id(audio_id)
        return audio_obj.to_dict() if audio_obj else None

    def get_random_audio(self) -> Optional[Dict[str, Any]]:
        """
        获取随机音色

        Returns:
            随机音色信息字典，不存在则返回 None
        """
        audio_obj = self._repository.get_random_active()
        return audio_obj.to_dict() if audio_obj else None
