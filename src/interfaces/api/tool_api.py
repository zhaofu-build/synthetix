"""
工具 API 模块

提供文件上传、配置管理等工具类 RESTful API 接口

路由前缀: /api/tools
"""
from fastapi import APIRouter, UploadFile, File, Depends
import os
from src import config
from src.application.services import use_ffmpeg
from src.shared.utils import file_util
from src.shared.models.base import BaseReq
from src.shared.models.response import success_response, error_response

router = APIRouter()


@router.post("/upload/video", summary="上传视频文件")
async def upload_video(file_stream: UploadFile = File(...)):
    """上传视频文件并获取视频信息"""
    file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
    video_info = use_ffmpeg.get_video_info(file_info["localPath"])
    return success_response(
        data={
            "webPath": file_info["webPath"],
            "localPath": file_info["localPath"],
            "duration": video_info["duration_hms"]
        },
        message="上传成功"
    )


@router.post("/upload/file", summary="上传通用文件")
async def upload_file(file_stream: UploadFile = File(...)):
    """上传通用文件"""
    file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
    return success_response(
        data={
            "webPath": file_info["webPath"],
            "localPath": file_info["localPath"]
        },
        message="上传成功"
    )


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
