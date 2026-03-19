"""
视频 API 模块

提供视频相关的 API 接口，包括视频素材管理、视频处理、字幕等功能
"""
import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, Query
from sqlalchemy.orm import Session

import config
from src.model.base import BaseReq
from src.model.response import success_response, error_response
from src.model.request import VideoUpdateRequest, VideoProcessRequest, TranscribeRequest
from src.db.session import get_db
from src.service.video_service import VideoService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_video_service(db: Session = Depends(get_db)) -> VideoService:
    """获取 VideoService 依赖"""
    return VideoService(db)


@router.post("/get_source_videos")
def get_source_videos(
    req: BaseReq,
    service: VideoService = Depends(get_video_service)
):
    """获取素材库素材（分页）"""
    from src.util.pagination import PaginatedQuery

    page_params = PaginatedQuery(page=req.current, page_size=req.size)

    # 构建查询
    filters = {}
    # 支持从请求中获取 video_type（如果存在）
    if hasattr(req, 'video_type') and req.video_type is not None:
        filters['video_type'] = req.video_type

    # 使用 Repository
    total = service.repository.count(filters=filters)
    items = service.repository.get_all(skip=page_params.offset, limit=page_params.limit, filters=filters)

    return success_response(
        data={
            "items": service.repository.bulk_to_dict(items),
            "total": total,
            "page": page_params.page,
            "page_size": page_params.page_size,
            "total_pages": (total + page_params.page_size - 1) // page_params.page_size
        },
        message="获取素材列表成功"
    )


@router.post("/update_video_source")
def update_video_description(
    req: VideoUpdateRequest,
    service: VideoService = Depends(get_video_service)
):
    """更新视频源信息"""
    # 构建更新参数
    update_data = {}
    if req.video_name is not None:
        update_data['video_name'] = req.video_name
    if req.web_path is not None:
        update_data['web_path'] = req.web_path
    if req.local_path is not None:
        update_data['local_path'] = req.local_path
    if req.duration is not None:
        update_data['duration'] = req.duration
    if req.duration_hms is not None:
        update_data['duration_hms'] = req.duration_hms
    if req.description is not None:
        update_data['description'] = req.description
    if req.video_type is not None:
        update_data['video_type'] = req.video_type
    if req.del_flag is not None:
        update_data['del_flag'] = req.del_flag

    video_obj = service.repository.update(req.id, **update_data)
    if video_obj:
        return success_response(data={"id": req.id}, message="更新成功")
    return error_response(error="NotFound", message=f"视频 {req.id} 不存在", code=404)


@router.post("/del_source_videos")
def del_source_videos(
    req: BaseReq,
    service: VideoService = Depends(get_video_service)
):
    """删除本地素材"""
    try:
        service.delete_video(req.id)
        return success_response(data={"id": req.id}, message="删除成功")
    except FileNotFoundError as e:
        return error_response(error="NotFound", message=str(e), code=404)


@router.post("/upload_source_videos_stream")
async def upload_source_videos_stream(
    file_stream: UploadFile = File(...),
    service: VideoService = Depends(get_video_service)
):
    """上传视频素材到数据库"""
    try:
        # 异步读取文件内容
        content = await file_stream.read()
        result = service.upload_video_file_from_bytes(
            file_content=content,
            filename=file_stream.filename or "video.mp4"
        )
        return success_response(data={"id": result["id"]}, message="上传成功")
    except (ValueError, IOError) as e:
        return error_response(error="UploadError", message=str(e), code=400)


@router.get("/get_description")
def get_description(
    id: int,
    service: VideoService = Depends(get_video_service)
):
    """获取视频描述（通过 AI 分析）"""
    video_obj = service.repository.get_by_id(id)
    if not video_obj:
        return error_response(error="NotFound", message=f"视频 {id} 不存在", code=404)

    # 解析视频描述
    try:
        from src.service.video_summary import video_summary
        description = video_summary(video_obj.local_path, None)
    except ImportError:
        logger.warning(f"video_summary 模块不可用，跳过描述生成")
        description = ""

    # 更新描述
    service.repository.update_description(id, description)
    return success_response(data={"description": description}, message="获取描述成功")


@router.post("/download_video")
async def download_video(req: BaseReq):
    """下载视频"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.download_video(req.video_url)
            return success_response(data=result, message="下载成功")
        except ValueError as e:
            return error_response(error="DownloadError", message=str(e), code=400)


@router.post("/process_video")
async def process_video(req: VideoProcessRequest):
    """处理视频（剪辑、变速、调整音量等）"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.process_video(
                input_path=req.input_path,
                output_format=req.output_format,
                start_time=req.start_time,
                end_time=req.end_time,
                duration=req.duration,
                speed_factor=req.speed,
                volume_factor=req.volume,
                width=req.width,
                height=req.height,
                cover_image=req.cover_image,
            )
            return success_response(data=result, message="处理成功")
        except FileNotFoundError:
            return error_response(error="FileNotFound", message="输入文件不存在", code=404)
        except ValueError as e:
            return error_response(error="ProcessError", message=str(e), code=400)


@router.post("/extract_frame")
async def extract_frame(req: BaseReq):
    """提取视频帧为图片"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.extract_frame(req.video_input, req.time_ss)
            return success_response(data=result, message="提取成功")
        except ValueError as e:
            return error_response(error="ExtractError", message=str(e), code=400)


@router.post("/get_audio")
async def get_audio(req: BaseReq):
    """从视频中提取音频"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.extract_audio(req.video_url)
            return success_response(data=result, message="提取成功")
        except ValueError as e:
            return error_response(error="ExtractError", message=str(e), code=400)


@router.post("/add_audio_to_video")
async def add_audio_to_video(req: BaseReq):
    """添加音频到视频"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.add_audio_to_video(req.video_path, req.audio_path)
            return success_response(data=result, message="添加成功")
        except ValueError as e:
            return error_response(error="MergeError", message=str(e), code=400)


@router.post("/transcribe")
async def transcribe(req: TranscribeRequest):
    """音视频转录生成字幕"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            subtitle_content = service.transcribe(
                input_path=req.input_path,
                model=req.model,
                output_format=req.output_format,
                is_translate=req.is_translate,
                subtitle_double=req.subtitle_double,
                translator_engine=req.translator_engine,
                subtitle_language=req.subtitle_language
            )
            return success_response(data={"subtitle_content": subtitle_content}, message="转录成功")
        except ValueError as e:
            return error_response(error="TranscribeError", message=str(e), code=400)


@router.post("/video_add_subtitle")
async def video_add_subtitle(req: BaseReq):
    """为视频添加字幕"""
    from src.db.session import get_db_context
    with get_db_context() as db:
        service = VideoService(db)
        try:
            result = service.add_subtitle(
                video_path=req.video_input,
                subtitle_content=req.subtitle_content,
                is_soft=req.is_soft,
                fontname=req.fontname,
                fontsize=req.fontsize,
                fontcolor=req.fontcolor,
                subtitle_bottom=req.subtitle_bottom
            )
            return success_response(data=result, message="添加字幕成功")
        except ValueError as e:
            return error_response(error="SubtitleError", message=str(e), code=400)


@router.post("/start_compression")
def start_compression(req: BaseReq):
    """启动批量视频压缩任务"""
    from src.util import file_util
    from src.service import use_ffmpeg

    logger.info("启动批量视频压缩任务")
    use_ffmpeg.batch_compress_videos(
        input_dir=file_util.format_windows_path(req.input_dir),
        backup_dir=file_util.format_windows_path(req.backup_dir),
        crf=req.crf,
        max_bitrate=req.max_bitrate
    )
    return success_response(message="压缩任务已启动")


@router.get("/get_random_video")
def get_random_video(
    video_type: Optional[int] = Query(None, description="视频类型"),
    service: VideoService = Depends(get_video_service)
):
    """获取随机视频"""
    video_obj = service.repository.get_random_active(video_type=video_type)
    if video_obj:
        return success_response(data=service.repository.to_dict(video_obj), message="获取成功")
    return error_response(error="NotFound", message="没有可用的视频", code=404)
