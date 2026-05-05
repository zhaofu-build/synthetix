"""
视频服务层

封装视频相关的业务逻辑，包括视频上传、下载、处理等
"""
import os
import uuid
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session

from src import config
from src.application.services import (
    ffmpeg_adapter as use_ffmpeg,
    whisper_adapter as use_fast_whisper,
    video_downloader_adapter as video_downloader
)
from src.shared.utils import time_util, file_util
from src.infrastructure.repositories import VideoRepository

logger = logging.getLogger(__name__)


class VideoService:
    """视频服务类"""

    def __init__(self, db: Session):
        """
        初始化视频服务

        Args:
            db: 数据库会话
        """
        self.db = db
        self._repository = VideoRepository(db)

    def upload_video_file(
        self,
        file_stream,
        filename: str,
        upload_dir: str = None
    ) -> Dict[str, Any]:
        """
        上传视频文件并保存到数据库

        Args:
            file_stream: 上传的文件流
            filename: 原始文件名
            upload_dir: 上传目录，默认使用配置中的目录

        Returns:
            包含视频 ID 和文件信息的字典

        Raises:
            ValueError: 文件处理失败
            IOError: 文件写入失败
        """
        if upload_dir is None:
            upload_dir = config.source_videos_dir

        # 确保目录存在
        os.makedirs(upload_dir, exist_ok=True)

        # 获取文件扩展名
        file_ext = filename.split('.')[-1] if filename and '.' in filename else 'mp4'
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)

        # 分块写入文件
        chunk_size = config.FILE_UPLOAD_CHUNK_SIZE if hasattr(config, 'FILE_UPLOAD_CHUNK_SIZE') else 1024 * 1024
        try:
            with open(file_path, "wb") as buffer:
                while True:
                    # 适配同步和异步读取
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

        # 视频入库时统一编码标准化
        use_ffmpeg.standardize_video(file_path)

        # 获取视频信息
        access_url_path = Path(file_path)
        try:
            video_info = use_ffmpeg.get_video_info(access_url_path)
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            # 清理已上传的文件
            file_util.del_file(file_path)
            raise ValueError(f"获取视频信息失败: {e}")

        # 保存到数据库
        web_path = upload_dir if upload_dir.endswith('/') else upload_dir + '/'
        web_path += unique_filename

        video_obj = self._repository.create(
            video_name=unique_filename,
            web_path=web_path,
            local_path=str(access_url_path),
            duration=video_info.get("duration", "0"),
            duration_hms=video_info.get("duration_hms", "00:00:00"),
        )

        logger.info(f"视频上传成功: ID={video_obj.id}, 文件名={unique_filename}")
        return {
            "id": video_obj.id,
            "filename": unique_filename,
            "web_path": web_path,
            "local_path": str(access_url_path),
            "duration": video_info.get("duration_hms", "00:00:00")
        }

    def upload_video_file_from_bytes(
        self,
        file_content: bytes,
        filename: str,
        upload_dir: str = None
    ) -> Dict[str, Any]:
        """
        从字节数据上传视频文件并保存到数据库

        Args:
            file_content: 文件内容（字节）
            filename: 原始文件名
            upload_dir: 上传目录，默认使用配置中的目录

        Returns:
            包含视频 ID 和文件信息的字典

        Raises:
            ValueError: 文件处理失败
            IOError: 文件写入失败
        """
        if upload_dir is None:
            upload_dir = config.source_videos_dir

        # 确保目录存在
        os.makedirs(upload_dir, exist_ok=True)

        # 获取文件扩展名
        file_ext = filename.split('.')[-1] if filename and '.' in filename else 'mp4'
        unique_filename = f"{uuid.uuid4().hex}.{file_ext}"
        file_path = os.path.join(upload_dir, unique_filename)

        # 写入文件
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
        except Exception as e:
            logger.error(f"文件写入失败: {e}")
            raise IOError(f"文件写入失败: {e}")

        # 视频入库时统一编码标准化
        use_ffmpeg.standardize_video(file_path)

        # 获取视频信息
        access_url_path = Path(file_path)
        try:
            video_info = use_ffmpeg.get_video_info(access_url_path)
        except Exception as e:
            logger.error(f"获取视频信息失败: {e}")
            # 清理已上传的文件
            file_util.del_file(file_path)
            raise ValueError(f"获取视频信息失败: {e}")

        # 保存到数据库
        web_path = upload_dir if upload_dir.endswith('/') else upload_dir + '/'
        web_path += unique_filename

        video_obj = self._repository.create(
            video_name=unique_filename,
            web_path=web_path,
            local_path=str(access_url_path),
            duration=video_info.get("duration", "0"),
            duration_hms=video_info.get("duration_hms", "00:00:00"),
        )

        logger.info(f"视频上传成功: ID={video_obj.id}, 文件名={unique_filename}, 原文件名={filename}")
        return {
            "id": video_obj.id,
            "filename": unique_filename,
            "web_path": web_path,
            "local_path": str(access_url_path),
            "duration": video_info.get("duration_hms", "00:00:00")
        }

    def download_video(self, video_url: str, output_dir: str = None, tags: str = None) -> Dict[str, Any]:
        """
        从 URL 下载视频并保存到素材库

        Args:
            video_url: 视频 URL
            output_dir: 输出目录，默认使用上传目录
            tags: 标签，逗号分隔

        Returns:
            包含文件路径、时长和数据库 ID 的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        try:
            title, duration = video_downloader.download_videos_from_url(video_url, output_dir)
        except Exception as e:
            logger.error(f"视频下载失败: {e}")
            raise ValueError(f"视频下载失败: {e}")

        # 视频入库时统一编码标准化
        access_url_path = Path(output_dir) / title
        use_ffmpeg.standardize_video(str(access_url_path))

        # 转换时长格式
        try:
            duration_hms = time_util.seconds_to_hms(duration)
        except (ValueError, TypeError):
            duration_hms = "00:00:00"

        # 获取视频详细信息
        try:
            video_info = use_ffmpeg.get_video_info(access_url_path)
            duration_hms = video_info.get("duration_hms", duration_hms)
        except Exception:
            video_info = {}

        # 保存到数据库
        web_path = output_dir if output_dir.endswith('/') else output_dir + '/'
        web_path += title

        video_obj = self._repository.create(
            video_name=title,
            web_path=web_path,
            local_path=str(access_url_path),
            duration=video_info.get("duration", str(duration) if duration else "0"),
            duration_hms=duration_hms,
            tags=tags,
        )

        logger.info(f"视频下载入库: ID={video_obj.id}, 文件名={title}")
        return {
            "id": video_obj.id,
            "filename": title,
            "web_path": web_path,
            "local_path": str(access_url_path),
            "duration": duration_hms
        }

    def process_video(
        self,
        input_path: str,
        output_format: str = "mp4",
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        duration: Optional[str] = None,
        speed_factor: Optional[float] = None,
        volume_factor: Optional[float] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        cover_image: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        处理视频（剪辑、变速、调整音量等）

        Args:
            input_path: 输入文件路径
            output_format: 输出格式
            start_time: 开始时间 (HH:MM:SS 或秒数)
            end_time: 结束时间 (HH:MM:SS 或秒数)
            duration: 时长
            speed_factor: 变速倍数
            volume_factor: 音量倍数
            width: 输出宽度
            height: 输出高度
            cover_image: 封面图路径

        Returns:
            包含输出文件路径和视频信息的字典

        Raises:
            FileNotFoundError: 输入文件不存在
            ValueError: 参数验证失败
        """
        # 验证输入路径
        input_file = Path(input_path)
        if not input_file.exists():
            raise FileNotFoundError(f"输入文件不存在: {input_path}")

        # 生成输出路径
        output_path = input_file.parent / f"{input_file.stem}_processed.{output_format}"

        # 调用 FFmpeg 处理
        try:
            output_path = use_ffmpeg.process_video(
                input_path=str(input_file),
                output_path=str(output_path),
                start_time=start_time,
                end_time=end_time,
                duration=duration,
                speed_factor=speed_factor,
                volume_factor=volume_factor,
                width=width,
                height=height,
                cover_image=cover_image,
                output_format=output_format
            )
        except Exception as e:
            logger.error(f"视频处理失败: {e}")
            raise ValueError(f"视频处理失败: {e}")

        # 获取处理后的视频信息
        try:
            video_info = use_ffmpeg.get_video_info(output_path)
        except Exception as e:
            logger.warning(f"获取视频信息失败: {e}")
            video_info = {"duration_hms": "00:00:00"}

        # 生成 web 路径
        web_filename = f"{input_file.stem}_processed.{output_format}"

        return {
            "filename": web_filename,
            "web_path": config.UPLOAD_DIR + web_filename,
            "local_path": str(output_path),
            "duration": video_info.get("duration_hms", "00:00:00")
        }

    def extract_frame(
        self,
        video_path: str,
        time_ss: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        提取视频帧为图片

        Args:
            video_path: 视频文件路径
            time_ss: 提取时间点 (秒数或 HH:MM:SS)
            output_dir: 输出目录

        Returns:
            包含文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        # 生成输出文件名
        timestamp = int(time.time())
        filename = f"extracted_frame_{timestamp}.png"
        output_path = Path(config.ROOT_DIR_WIN) / output_dir / filename

        try:
            use_ffmpeg.extract_frame(video_path, time_ss, output_path)
        except Exception as e:
            logger.error(f"提取帧失败: {e}")
            raise ValueError(f"提取帧失败: {e}")

        return {
            "filename": filename,
            "web_path": output_dir + filename,
            "local_path": str(output_path)
        }

    def extract_audio(
        self,
        video_path: str,
        output_filename: str = "distill_audio.mp3",
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        从视频中提取音频

        Args:
            video_path: 视频文件路径
            output_filename: 输出文件名
            output_dir: 输出目录

        Returns:
            包含文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        output_path = Path(config.ROOT_DIR_WIN) / output_dir / output_filename

        try:
            use_ffmpeg.get_audio(video_path, output_path)
        except Exception as e:
            logger.error(f"提取音频失败: {e}")
            raise ValueError(f"提取音频失败: {e}")

        return {
            "filename": output_filename,
            "audio_path": output_dir + output_filename,
            "web_path": output_dir + output_filename,
            "local_path": str(output_path)
        }

    def add_audio_to_video(
        self,
        video_path: str,
        audio_path: str,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        添加音频到视频

        Args:
            video_path: 视频文件路径
            audio_path: 音频文件路径
            output_dir: 输出目录

        Returns:
            包含文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        # 生成输出文件名
        timestamp = int(time.time())
        filename = f"video_with_audio_{timestamp}.mp4"
        output_path = Path(config.ROOT_DIR_WIN) / output_dir / filename

        try:
            use_ffmpeg.add_audio_to_video(video_path, audio_path, output_path)
        except Exception as e:
            logger.error(f"添加音频失败: {e}")
            raise ValueError(f"添加音频失败: {e}")

        return {
            "filename": filename,
            "web_path": output_dir + filename,
            "local_path": str(output_path)
        }

    def transcribe(
        self,
        input_path: str,
        output_format: str = "srt",
        is_translate: bool = False,
        subtitle_double: bool = False,
        translator_engine: str = "google",
        subtitle_language: str = "zh"
    ) -> str:
        """
        音视频转录生成字幕

        Args:
            input_path: 输入文件路径
            output_format: 输出格式
            is_translate: 是否翻译
            subtitle_double: 字幕双语
            translator_engine: 翻译引擎
            subtitle_language: 字幕语言

        Returns:
            字幕内容字符串
        """
        try:
            subtitle_content = use_fast_whisper.transcribe(
                input_path,
                output_format,
                is_translate,
                subtitle_double,
                translator_engine,
                subtitle_language
            )
            return subtitle_content
        except Exception as e:
            logger.error(f"转录失败: {e}")
            raise ValueError(f"转录失败: {e}")

    def add_subtitle(
        self,
        video_path: str,
        subtitle_content: str,
        is_soft: bool = False,
        fontname: str = "楷体",
        fontsize: int = 16,
        fontcolor: str = "&Hffffff",
        fontbordercolor: str = "&H000000",
        subtitle_bottom: int = 20,
        bold: bool = False,
        outline_width: float = 1,
        shadow: float = 0,
        alignment: int = 2,
        bg_color: str = None,
        margin_l: int = 10,
        margin_r: int = 10,
        output_dir: str = None
    ) -> Dict[str, str]:
        """
        为视频添加字幕

        Args:
            video_path: 视频文件路径
            subtitle_content: 字幕内容
            is_soft: 是否为软字幕
            fontname: 字体名称
            fontsize: 字体大小
            fontcolor: 字体颜色
            fontbordercolor: 描边颜色
            subtitle_bottom: 字幕底部边距
            bold: 粗体
            outline_width: 描边宽度
            shadow: 阴影深度
            alignment: 位置 (2=底部居中 5=上方居中 8=居中)
            bg_color: 背景颜色
            margin_l: 左边距
            margin_r: 右边距
            output_dir: 输出目录

        Returns:
            包含文件路径的字典
        """
        if output_dir is None:
            output_dir = config.UPLOAD_DIR

        os.makedirs(output_dir, exist_ok=True)

        try:
            title = use_ffmpeg.add_subtitle(
                video_path,
                subtitle_content,
                is_soft,
                fontname=fontname,
                fontsize=fontsize,
                fontcolor=fontcolor,
                fontbordercolor=fontbordercolor,
                subtitle_bottom=subtitle_bottom,
                bold=bold,
                outline_width=outline_width,
                shadow=shadow,
                alignment=alignment,
                bg_color=bg_color,
                margin_l=margin_l,
                margin_r=margin_r,
            )
            output_path = Path(config.ROOT_DIR_WIN) / output_dir / title
            video_info = use_ffmpeg.get_video_info(output_path)

            return {
                "filename": title,
                "web_path": config.UPLOAD_DIR + title,
                "local_path": str(output_path),
                "duration": video_info.get("duration_hms", "00:00:00")
            }
        except Exception as e:
            logger.error(f"添加字幕失败: {e}")
            raise ValueError(f"添加字幕失败: {e}")

    def delete_video(self, video_id: int) -> bool:
        """
        删除视频（包括文件和数据库记录）

        Args:
            video_id: 视频 ID

        Returns:
            删除成功返回 True

        Raises:
            FileNotFoundError: 视频不存在
        """
        video_obj = self._repository.get_by_id(video_id)
        if not video_obj:
            raise FileNotFoundError(f"视频 {video_id} 不存在")

        # 删除文件
        if video_obj.local_path:
            file_util.del_file(video_obj.local_path)

        # 删除数据库记录
        self._repository.delete(video_id)
        logger.info(f"视频已删除: ID={video_id}")
        return True

    def get_paginated_videos(
        self,
        page: int = 1,
        page_size: int = 10,
        video_type: Optional[int] = None,
        include_temp: bool = False
    ) -> Dict[str, Any]:
        """
        获取分页视频列表

        Args:
            page: 页码
            page_size: 每页大小
            video_type: 视频类型过滤（可选）
            include_temp: 是否包含临时素材（默认不包含）

        Returns:
            包含 items, total, page, page_size, total_pages 的字典
        """
        if include_temp:
            filters = {}
            if video_type is not None:
                filters['video_type'] = video_type
            total = self._repository.count(filters=filters)
            skip = (page - 1) * page_size
            items = self._repository.get_all(skip=skip, limit=page_size, filters=filters)
        else:
            skip = (page - 1) * page_size
            items = self._repository.get_library_videos(skip=skip, limit=page_size, video_type=video_type)
            total = self._repository.count_library_videos(video_type=video_type)

        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return {
            "items": self._repository.bulk_to_dict(items),
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages
        }

    def get_video_by_id(self, video_id: int) -> Optional[Dict[str, Any]]:
        """
        根据 ID 获取视频信息

        Args:
            video_id: 视频 ID

        Returns:
            视频信息字典，不存在则返回 None
        """
        video_obj = self._repository.get_by_id(video_id)
        return video_obj.to_dict() if video_obj else None

    def get_random_video(self, video_type: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        获取随机视频

        Args:
            video_type: 视频类型过滤（可选）

        Returns:
            随机视频信息字典，不存在则返回 None
        """
        video_obj = self._repository.get_random_active(video_type=video_type)
        return video_obj.to_dict() if video_obj else None

    def update_video(self, video_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """
        更新视频信息

        Args:
            video_id: 视频 ID
            **kwargs: 要更新的属性

        Returns:
            更新后的视频信息字典，不存在则返回 None
        """
        video_obj = self._repository.update(video_id, **kwargs)
        return video_obj.to_dict() if video_obj else None

    def update_video_description(self, video_id: int, description: str) -> bool:
        """
        更新视频描述

        Args:
            video_id: 视频 ID
            description: 新的描述内容

        Returns:
            更新成功返回 True
        """
        return self._repository.update_description(video_id, description) is not None
