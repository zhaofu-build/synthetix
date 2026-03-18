from src.service import use_fast_whisper, use_ffmpeg
from src.util import time_util, file_util
from fastapi import APIRouter, UploadFile, File, Depends
from src.model.base import BaseReq
from src.model.entity.video_source import VideoSource as VideoSourceEntity
from src.db.session import get_db
from sqlalchemy.orm import Session
from sqlalchemy import func
from pathlib import Path
import time
import config
import logging as logger
import os
import uuid
from src.service.use_qwen_vl import video_summary

router = APIRouter()


@router.post("/get_source_videos")
def get_source_videos(req: BaseReq, db: Session = Depends(get_db)):
    # 获取素材库素材
    query = db.query(VideoSourceEntity)
    if req.video_type is not None:
        query = query.filter(VideoSourceEntity.video_type == req.video_type)
    video_objs = query.all()
    
    result = []
    for obj in video_objs:
        video_dict = {
            "id": obj.id,
            "video_name": obj.video_name,
            "web_path": obj.web_path,
            "local_path": obj.local_path,
            "duration": obj.duration,
            "duration_hms": obj.duration_hms,
            "description": obj.description,
            "video_type": obj.video_type,
            "create_time": obj.create_time,
            "del_flag": obj.del_flag,
        }
        result.append(video_dict)
    return result


@router.post("/update_video_source")
def update_video_description(req: BaseReq, db: Session = Depends(get_db)):
    # 修改
    # 从请求体中获取参数
    video_id = req.id
    video_name = getattr(req, 'video_name', None)
    web_path = getattr(req, 'web_path', None)
    local_path = getattr(req, 'local_path', None)
    duration = getattr(req, 'duration', None)
    duration_hms = getattr(req, 'duration_hms', None)
    description = getattr(req, 'description', None)
    video_type = getattr(req, 'video_type', None)
    del_flag = getattr(req, 'del_flag', None)
    
    video_obj = db.query(VideoSourceEntity).filter(VideoSourceEntity.id == video_id).first()
    if video_obj:
        # 更新现有记录
        if video_name is not None:
            video_obj.video_name = video_name
        if web_path is not None:
            video_obj.web_path = web_path
        if local_path is not None:
            video_obj.local_path = local_path
        if duration is not None:
            video_obj.duration = duration
        if duration_hms is not None:
            video_obj.duration_hms = duration_hms
        if description is not None:
            video_obj.description = description
        if video_type is not None:
            video_obj.video_type = video_type
        if del_flag is not None:
            video_obj.del_flag = del_flag
        db.commit()
        db.refresh(video_obj)
        return video_obj
    else:
        # 创建新记录
        video_obj = VideoSourceEntity(
            video_name=video_name,
            web_path=web_path,
            local_path=local_path,
            duration=duration,
            duration_hms=duration_hms,
            description=description,
            video_type=video_type,
            del_flag=del_flag
        )
        db.add(video_obj)
        db.commit()
        db.refresh(video_obj)
        return video_obj


@router.post("/del_source_videos")
def del_source_videos(req: BaseReq, db: Session = Depends(get_db)):
    # 删除本地素材
    video_obj = db.query(VideoSourceEntity).filter(VideoSourceEntity.id == req.id).first()
    if video_obj:
        file_util.del_file(video_obj.local_path)
        db.delete(video_obj)
        db.commit()
        return True
    return False


# @router.post("/del_all_source_videos")
# def del_source_videos():
#     # 删除全部本地素材
#     return file_util.del_file(config.source_videos_dir)


# 上传视频素材
@router.post("/upload_source_videos_stream")
async def upload_source_videos_stream(file_stream: UploadFile = File(...), db: Session = Depends(get_db)):
    """上传视频素材到数据库"""
    # 生成唯一文件名
    file_ext = file_stream.filename.split('.')[-1] if file_stream.filename else 'mp4'
    filename = f"{uuid.uuid4().hex}.{file_ext}"
    file_path = os.path.join(config.source_videos_dir, filename)

    # 分块写入文件
    chunk_size = 1024 * 1024
    with open(file_path, "wb") as buffer:
        while content := await file_stream.read(chunk_size):
            buffer.write(content)

    access_url_path = config.ROOT_DIR_WIN / config.source_videos_dir / filename
    video_info = use_ffmpeg.get_video_info(access_url_path)

    # 创建数据库记录
    video_obj = VideoSourceEntity(
        video_name=filename,
        web_path=config.source_videos_dir + filename,
        local_path=str(access_url_path),
        duration=video_info["duration"],
        duration_hms=video_info["duration_hms"],
    )
    db.add(video_obj)
    db.commit()
    db.refresh(video_obj)
    return True

@router.get("/get_description")
def get_description(id: int, db: Session = Depends(get_db)):
    video_obj = db.query(VideoSourceEntity).filter(VideoSourceEntity.id == id).first()
    if not video_obj:
        return None
    # 解析视频描述
    description = video_summary(video_obj.local_path, None)
    # 更新描述
    video_obj.description = description
    db.commit()
    db.refresh(video_obj)
    return description

# 下载视频
@router.post("/download_video")
async def download_video(req: BaseReq):
    title, duration = video_downloader.download_videos_from_url(req.video_url, config.UPLOAD_DIR)
    access_url_path = config.ROOT_DIR_WIN / "static" / "uploads" / title
    # video_info = use_ffmpeg.get_info(access_url_path)
    # 转换时长格式
    try:
        duration = time_util.seconds_to_hms(duration)
    except (ValueError, TypeError):
        duration = "00:00:00"  # 异常时返回默认值
    return {
        "videoWebPath": config.UPLOAD_DIR + title,
        "videoPath": access_url_path,
        "duration": duration
        # "duration": video_info["duration"]
    }


# 视频处理
@router.post("/process_video")
async def process_video(req: BaseReq):
    # 验证文件路径
    if not Path(req.input_path).exists():
        return {"error": "文件不存在"}
    input_path = getattr(req, 'input_path', None)
    output_format = getattr(req, 'output_format', 'mp4')
    # 生成默认输出路径
    input_file = Path(input_path)
    output_path = input_file.parent / f"{input_file.stem}_processed.{output_format}"

    output_path = use_ffmpeg.process_video(
        input_path=input_path,
        output_path=output_path,
        start_time=getattr(req, 'start_time', None),
        end_time=getattr(req, 'end_time', None),
        duration=getattr(req, 'duration', None),
        speed_factor=getattr(req, 'speed', None),
        volume_factor=getattr(req, 'volume', None),
        width=getattr(req, 'width', None),
        height=getattr(req, 'height', None),
        cover_image=getattr(req, 'cover_image', None),
        output_format=output_format
    )
    video_info = use_ffmpeg.get_video_info(output_path)
    return {
        "videoWebPath": config.UPLOAD_DIR + f"{input_file.stem}_processed.{output_format}",
        "videoPath": output_path,
        "duration": video_info["duration_hms"]
    }


# 提取图片
@router.post("/extract_frame")
async def extract_frame(req: BaseReq):
    # 生成唯一文件名
    timestamp = int(time.time())
    filename = f"extracted_frame_{timestamp}.png"
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / filename
    use_ffmpeg.extract_frame(req.video_input, req.time_ss, access_url_path)
    return {
        "webPath": config.UPLOAD_DIR + filename,
        "localPath": access_url_path,
    }


# # 设置封面图
# @router.post("/set_video_cover")
# async def set_video_cover(req: BaseReq):
#     video_path = save_upload_file(req.video_input, ".mp4")
#     cover_path = save_upload_file(req.cover_image, ".jpg")
#     output_path = use_ffmpeg.set_video_cover(video_path, cover_path)
#     return FileResponse(output_path, filename="with_cover.mp4")
#


# 提取音频
@router.post("/get_audio")
async def get_audio(req: BaseReq):
    output_dir = config.ROOT_DIR_WIN / config.UPLOAD_DIR / 'distill_audio.mp3'
    use_ffmpeg.get_audio(req.video_url, output_dir)
    return {
        "audioPath": config.UPLOAD_DIR + "distill_audio.mp3",
        "audioWebPath": config.UPLOAD_DIR + "distill_audio.mp3"
    }


# 添加音频到视频
@router.post("/add_audio_to_video")
async def add_audio_to_video(req: BaseReq):
    # 生成唯一文件名
    timestamp = int(time.time())
    filename = f"video_with_audio_{timestamp}.mp4"
    output_dir = config.ROOT_DIR_WIN / config.UPLOAD_DIR / filename
    use_ffmpeg.add_audio_to_video(req.video_path, req.audio_path, output_dir)
    return {
        "webPath": config.UPLOAD_DIR + filename,
        "localPath": f"{output_dir}"
    }


# 音视频转录
@router.post("/transcribe")
async def transcribe(req: BaseReq):
    subtitle_content = use_fast_whisper.transcribe(
        req.input_path, req.model,
        req.output_format, req.is_translate, req.subtitle_double,
        req.translator_engine, req.subtitle_language
    )
    return {
        "subtitle_content": subtitle_content
    }


# 视频添加字幕
@router.post("/video_add_subtitle")
async def video_add_subtitle(req: BaseReq):
    title = use_ffmpeg.add_subtitle(req.video_input, req.subtitle_content, req.is_soft, req.fontname, req.fontsize,
                                    req.fontcolor, req.subtitle_bottom)
    access_url_path = config.ROOT_DIR_WIN / config.UPLOAD_DIR / title
    video_info = use_ffmpeg.get_video_info(access_url_path)
    return {
        "videoWebPath": config.UPLOAD_DIR + title,
        "videoPath": access_url_path,
        "duration": video_info["duration_hms"]
    }


@router.post("/start_compression")
def start_compression(req: BaseReq):
    logger.info("启动批量视频压缩任务")
    use_ffmpeg.batch_compress_videos(
        input_dir=file_util.format_windows_path(req.input_dir),
        backup_dir=file_util.format_windows_path(req.backup_dir),
        crf=req.crf,
        max_bitrate=req.max_bitrate
    )
    return True


# 获取随机视频
@router.get("/get_random_video")
def get_random_video(db: Session = Depends(get_db)):
    video_obj = db.query(VideoSourceEntity).filter(
        VideoSourceEntity.del_flag == False
    ).order_by(func.random()).limit(1).first()
    if video_obj:
        video_dict = {
            "id": video_obj.id,
            "video_name": video_obj.video_name,
            "web_path": video_obj.web_path,
            "local_path": video_obj.local_path,
            "duration": video_obj.duration,
            "duration_hms": video_obj.duration_hms,
            "description": video_obj.description,
            "video_type": video_obj.video_type,
            "create_time": video_obj.create_time,
            "del_flag": video_obj.del_flag,
        }
        return video_dict
    return None
