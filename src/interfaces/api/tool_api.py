"""
工具 API 模块

提供文件上传、配置管理等工具类 RESTful API 接口

路由前缀: /api/tools
"""
import os
import logging
from typing import Dict, Any
from fastapi import APIRouter, UploadFile, File, Form

from src import config
from src.application.services import use_ffmpeg
from src.shared.utils import file_util
from src.shared.models.response import success_response, error_response
from src.shared.exceptions.exceptions import ValidationException, ResourceNotFoundException, ExternalServiceException
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

    file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
    video_info = use_ffmpeg.get_video_info(file_info["local_path"])

    return success_response(
        data={
            "web_path": file_info["web_path"],
            "duration": video_info.get("duration_hms", "00:00:00")
        },
        message="上传成功"
    )


# 允许的通用文件类型
_ALLOWED_FILE_EXT = {
    ".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".ts",
    ".mp3", ".wav", ".flac", ".aac", ".m4a", ".ogg", ".wma",
    ".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg",
    ".srt", ".ass", ".vtt", ".txt", ".json",
}


@router.post("/upload/file", summary="上传通用文件")
async def upload_file(
    file_stream: UploadFile = File(...),
    project_id: int = Form(default=None),
    session_id: str = Form(default=None),
):
    """上传文件到项目临时目录"""
    # 校验文件类型
    ext = os.path.splitext(file_stream.filename or "")[1].lower()
    if ext not in _ALLOWED_FILE_EXT:
        return error_response(error="UploadError", message=f"不支持的文件格式: {ext}", code=400)

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

    # 确定保存目录：优先项目临时目录，回退到通用目录
    if project_id:
        temp_dir = os.path.join(str(config.ROOT_DIR_WIN), "static", "temp", str(project_id))
        os.makedirs(temp_dir, exist_ok=True)
        prefix = "upload"
    else:
        temp_dir = str(config.source_videos_dir)
        prefix = "upload"

    file_info = await file_util.save_uploaded_file(file_stream, temp_dir)
    filename = file_info["filename"]
    local_path = file_info["local_path"]
    web_path = f"/static/temp/{project_id}/{filename}" if project_id else f"/static/source_videos/{filename}"

    # 视频入库时统一编码标准化
    if file_type == "video":
        use_ffmpeg.standardize_video(local_path)

    # 存入项目临时文件表 + 创建 VideoSource 记录（供工具引用）
    temp_file_id = None
    video_id = None
    if project_id:
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.temp_file_repository import TempFileRepository
        from src.infrastructure.repositories import VideoRepository
        file_size = os.path.getsize(local_path) if os.path.isfile(local_path) else 0
        with get_db_context() as db:
            # 临时文件记录（用于级联删除）
            repo = TempFileRepository(db)
            record = repo.create(
                project_id=project_id,
                session_id=session_id,
                file_name=file_stream.filename or filename,
                file_path=local_path,
                web_path=web_path,
                file_type=file_type,
                source="upload",
                file_size=file_size,
            )
            temp_file_id = record.id
            # 同时创建 VideoSource 记录（is_temp=True），供工具通过 video_id 引用
            video_repo = VideoRepository(db)
            vs = video_repo.create(
                video_name=file_stream.filename or filename,
                local_path=local_path,
                web_path=web_path,
                is_temp=True,
                file_type=file_type,
            )
            video_id = vs.id
            db.commit()

    return success_response(
        data={
            "temp_file_id": temp_file_id,
            "video_id": video_id,
            "web_path": web_path,
            "file_type": file_type,
        },
        message="上传成功"
    )


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

    # 同步 core_nexus API Key 到运行时配置和客户端
    if "core_nexus.api_key" in config_data:
        api_key = config_data["core_nexus.api_key"]
        config.llm_key = api_key  # config.py 中定义的小写变量名
        if not getattr(config, "TTS_KEY", ""):
            config.TTS_KEY = api_key
        if not getattr(config, "ASR_KEY", ""):
            config.ASR_KEY = api_key
        if not getattr(config, "VL_KEY", ""):
            config.VL_KEY = api_key
        from src.shared.utils.core_nexus_client import reset_client
        reset_client()

    # 同步视频 API Key 到运行时配置
    if "pixabay_api_key" in config_data:
        config.pixabay_api_key = config_data["pixabay_api_key"]
    if "video_api_keys" in config_data:
        config.video_api_keys = config_data["video_api_keys"]

    # 同步新闻 API Key 到运行时配置
    if "tian_api_key" in config_data:
        config.TIAN_API_KEY = config_data["tian_api_key"]
    if "news_api_key" in config_data:
        config.NEWS_API_KEY = config_data["news_api_key"]

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
    with open(COOKIE_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    return success_response(data={"exists": True, "content": content}, message="获取成功")


@router.put("/cookies", summary="保存 Cookie 文件")
async def save_cookies(req: Dict[str, Any]):
    content = req.get("content", "")
    with open(COOKIE_FILE, "w", encoding="utf-8") as f:
        f.write(content)
    return success_response(message="Cookie 已保存")


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
