"""
工具 API 模块

提供文件上传、配置管理等工具类 RESTful API 接口

路由前缀: /api/tools
"""
import os
import logging
from fastapi import APIRouter, UploadFile, File

from src import config
from src.application.services import use_ffmpeg
from src.shared.utils import file_util
from src.shared.models.base import BaseReq
from src.shared.models.response import success_response, error_response

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
    """上传通用文件"""
    # 校验文件类型
    ext = os.path.splitext(file_stream.filename or "")[1].lower()
    if ext not in _ALLOWED_FILE_EXT:
        return error_response(error="UploadError", message=f"不支持的文件格式: {ext}", code=400)

    try:
        file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)

        return success_response(
            data={
                "web_path": file_info["web_path"],
                "local_path": file_info["local_path"]
            },
            message="上传成功"
        )
    except Exception as e:
        logger.error(f"上传文件失败: {e}", exc_info=True)
        return error_response(error="UploadError", message=str(e), code=500)


@router.get("/config", summary="获取配置")
async def get_config():
    """获取系统配置"""
    config_info = file_util.load_config()
    return success_response(data=config_info, message="获取配置成功")


@router.patch("/config", summary="更新配置")
async def update_config(req: BaseReq):
    """更新系统配置"""
    config_data = req.dict(exclude_unset=True)
    for key, value in config_data.items():
        file_util.update_value(key, value)
    return success_response(data=True, message="保存配置成功")


@router.get("/logs", summary="获取日志")
async def get_logs():
    """获取系统日志"""
    # TODO: 实现日志读取功能
    return success_response(data="", message="获取日志成功")
