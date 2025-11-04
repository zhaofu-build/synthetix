from fastapi import APIRouter, UploadFile, File
import uuid, os
import config
from data import use_ffmpeg
from util import file_util
from db.Do import BaseReq
router = APIRouter()


# from data import find_duplicates
# # 查找重复文件
# @router.post("/find_duplicates")
# async def find_repeat_file(req: BaseReq):
#     folder_path = req.folder_path
#     duplicates = find_duplicates.run_duplicates(folder_path)
#     return result(0, duplicates)


@router.post("/upload_file_stream")
async def upload_file_stream(file_stream: UploadFile = File(...)):
    # 生成唯一文件名
    file_ext = file_stream.filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)

    # 分块写入文件（适合大文件）
    with open(file_path, "wb") as buffer:
        while content := await file_stream.read(1024 * 1024):  # 每次读取1MB
            buffer.write(content)
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / filename
    video_info = use_ffmpeg.get_video_info(access_url_path)
    return {
        "webPath": f"{config.UPLOAD_DIR}{filename}",
        "localPath": access_url_path,
        "duration": video_info["duration_hms"]
    }


@router.post("/upload_all_file_stream")
async def upload_img_file_stream(file_stream: UploadFile = File(...)):
    # 生成唯一文件名
    file_ext = file_stream.filename.split('.')[-1]
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(config.UPLOAD_DIR, filename)

    # 分块写入文件（适合大文件）
    with open(file_path, "wb") as buffer:
        while content := await file_stream.read(1024 * 1024):  # 每次读取1MB
            buffer.write(content)
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / filename
    return {
        "webPath": f"{config.UPLOAD_DIR}{filename}",
        "localPath": access_url_path
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
