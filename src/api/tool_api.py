from fastapi import APIRouter, UploadFile, File
import os
import config
from src.service import use_ffmpeg
from src.util import file_util
from src.model.base import BaseReq

router = APIRouter()


# from service import find_duplicates
# # 查找重复文件
# @router.post("/find_duplicates")
# async def find_repeat_file(req: BaseReq):
#     folder_path = req.folder_path
#     duplicates = find_duplicates.run_duplicates(folder_path)
#     return result(0, duplicates)


@router.post("/upload_file_stream")
async def upload_file_stream(file_stream: UploadFile = File(...)):
    """上传视频文件并获取视频信息"""
    file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
    video_info = use_ffmpeg.get_video_info(file_info["localPath"])
    return {
        "webPath": file_info["webPath"],
        "localPath": file_info["localPath"],
        "duration": video_info["duration_hms"]
    }


@router.post("/upload_all_file_stream")
async def upload_img_file_stream(file_stream: UploadFile = File(...)):
    """上传通用文件"""
    file_info = await file_util.save_uploaded_file(file_stream, config.UPLOAD_DIR)
    return {
        "webPath": file_info["webPath"],
        "localPath": file_info["localPath"]
    }


@router.get("/loadLog")
async def loadLog():
    return ""


@router.get("/get_config")
async def get_config():
    # 获取配置
    config_info = file_util.load_config()
    return config_info


@router.post("/save_config")
async def save_config(req: BaseReq):
    # 保存配置
    config_data = req.dict(exclude_unset=True)
    for key, value in config_data.items():
        file_util.update_value(key, value)
    return True
