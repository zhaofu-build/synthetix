"""
工具 API 模块

提供文件上传、配置管理等工具类 RESTful API 接口

路由前缀: /api/tools
"""
import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File

from src import config
from src.application.services import use_ffmpeg
from src.shared.utils import file_util
from src.shared.models.response import success_response, error_response
from src.shared.utils.config_manager import get as cfg_get, get_all as cfg_get_all, set_value as cfg_set, reload_config as cfg_reload

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/upload/video", summary="上传视频文件")
async def upload_video(file_stream: UploadFile = File(...)):
    """上传视频文件并获取视频信息"""
    # 校验文件类型
    ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".ts"}
    ext = os.path.splitext(file_stream.filename or "")[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        return error_response(error="UploadError", message=f"不支持的视频格式: {ext}", code=400)

    try:
        file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
        video_info = use_ffmpeg.get_video_info(file_info["local_path"])

        return success_response(
            data={
                "web_path": file_info["web_path"],
                "local_path": file_info["local_path"],
                "duration": video_info.get("duration_hms", "00:00:00")
            },
            message="上传成功"
        )
    except Exception as e:
        logger.error(f"上传视频失败: {e}", exc_info=True)
        return error_response(error="UploadError", message=str(e), code=500)


# 允许的通用文件类型
_ALLOWED_FILE_EXT = {
    ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".ts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".srt", ".ass", ".vtt", ".txt", ".json",
}


@router.post("/upload/file", summary="上传通用文件")
async def upload_file(file_stream: UploadFile = File(...)):
    """上传通用文件到正式素材目录并入库"""
    from src.infrastructure.repositories import VideoRepository

    # 校验文件类型
    ext = os.path.splitext(file_stream.filename or "")[1].lower()
    if ext not in _ALLOWED_FILE_EXT:
        return error_response(error="UploadError", message=f"不支持的文件格式: {ext}", code=400)

    try:
        file_info = await file_util.save_uploaded_file(file_stream, config.source_videos_dir)

        # 根据扩展名推断素材类型
        _VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".ts"}
        _AUDIO_EXT = {".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma"}
        _IMAGE_EXT = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
        if ext in _VIDEO_EXT:
            file_type = "video"
        elif ext in _AUDIO_EXT:
            file_type = "audio"
        elif ext in _IMAGE_EXT:
            file_type = "image"
        else:
            file_type = "document"

        # 入 DB 作为临时素材
        from src.infrastructure.db.session import get_db_context
        filename = file_info["filename"]
        with get_db_context() as db:
            repo = VideoRepository(db)
            new_video = repo.create(
                video_name=file_stream.filename or filename,
                local_path=file_info["local_path"],
                web_path=f"/static/source_videos/{filename}",
                is_temp=True,
                file_type=file_type,
            )
            video_id = new_video.id
            db.commit()

        return success_response(
            data={
                "video_id": video_id,
                "web_path": f"/static/source_videos/{filename}",
                "local_path": file_info["local_path"],
            },
            message="上传成功"
        )
    except Exception as e:
        logger.error(f"上传文件失败: {e}", exc_info=True)
        return error_response(error="UploadError", message=str(e), code=500)


@router.get("/config", summary="获取配置")
async def get_config():
    """获取系统配置（合并 default.json + settings.json）"""
    config_info = cfg_get_all()
    return success_response(data=config_info, message="获取配置成功")


@router.patch("/config", summary="更新配置")
async def update_config(req: Dict[str, Any]):
    """更新系统配置并持久化到 settings.json"""
    config_data = req
    for key, value in config_data.items():
        if key.startswith('_'):
            continue
        cfg_set(key, value)

    # 当 core_nexus.base_url 变更时，同步更新运行时配置和客户端
    if "core_nexus.base_url" in config_data:
        new_url = config_data["core_nexus.base_url"]
        if new_url:
            config.CORE_NEXUS_BASE_URL = new_url
        from src.shared.utils.core_nexus_client import reset_client
        reset_client()

    # 同步视频 API Key 到运行时配置
    if "pixabay_api_key" in config_data:
        config.pixabay_api_key = config_data["pixabay_api_key"]
    if "video_api_keys" in config_data:
        config.video_api_keys = config_data["video_api_keys"]

    return success_response(data=True, message="保存配置成功")


@router.post("/config/reload", summary="热更新配置")
async def reload_config():
    """重新加载配置文件（热更新，无需重启）"""
    cfg_reload()
    return success_response(data=cfg_get_all(), message="配置已重新加载")


COOKIE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "cookies.txt")


@router.get("/cookies", summary="获取 Cookie 文件内容")
async def get_cookies():
    if not os.path.exists(COOKIE_FILE):
        return success_response(data={"exists": False, "content": ""}, message="Cookie 文件不存在")
    try:
        with open(COOKIE_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        return success_response(data={"exists": True, "content": content}, message="获取成功")
    except Exception as e:
        return error_response(error="CookieError", message=str(e), code=500)


@router.put("/cookies", summary="保存 Cookie 文件")
async def save_cookies(req: Dict[str, Any]):
    content = req.get("content", "")
    try:
        with open(COOKIE_FILE, "w", encoding="utf-8") as f:
            f.write(content)
        return success_response(message="Cookie 已保存")
    except Exception as e:
        return error_response(error="CookieError", message=str(e), code=500)


@router.delete("/cookies", summary="删除 Cookie 文件")
async def delete_cookies():
    if os.path.exists(COOKIE_FILE):
        os.remove(COOKIE_FILE)
    return success_response(message="Cookie 已删除")


@router.get("/logs", summary="获取日志")
async def get_logs():
    """获取系统日志"""
    # TODO: 实现日志读取功能
    return success_response(data="", message="获取日志成功")
