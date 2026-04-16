"""
视频 API 模块

提供视频相关的 RESTful API 接口，包括视频素材管理、视频处理、字幕等功能

路由前缀: /api/videos

注意：路由顺序很重要！静态路由必须在动态路由（/{video_id}）之前定义。
"""
import os
import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, UploadFile, File, Depends, Query, Path as PathParam
from sqlalchemy.orm import Session

from src import config
from src.shared.models.response import success_response, error_response
from src.shared.models.request import VideoUpdateRequest, VideoProcessRequest, TranscribeRequest
from src.interfaces.api.schemas.video_schemas import (
    VideoDownloadRequest,
    VideoExtractFrameRequest,
    VideoExtractAudioRequest,
    VideoAddAudioRequest,
    VideoAddSubtitleRequest,
    BatchCompressRequest,
)
from src.infrastructure.db.session import get_db
from src.application.services.video_service import VideoService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_video_service(db: Session = Depends(get_db)) -> VideoService:
    """获取 VideoService 依赖"""
    return VideoService(db)


# ==================== 视频素材管理 - 静态路由（必须在动态路由之前） ====================

@router.get("", summary="获取视频列表")
def get_videos(
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=10, ge=1, le=100, description="每页大小"),
    video_type: Optional[int] = Query(None, description="视频类型"),
    service: VideoService = Depends(get_video_service)
):
    """获取视频素材列表（分页）"""
    result = service.get_paginated_videos(page=page, page_size=page_size, video_type=video_type)
    return success_response(data=result, message="获取素材列表成功")


@router.post("", summary="上传视频")
async def upload_video(
    file_stream: UploadFile = File(...),
    service: VideoService = Depends(get_video_service)
):
    """上传视频素材"""
    # 校验文件类型
    ALLOWED_VIDEO_EXT = {".mp4", ".avi", ".mov", ".mkv", ".flv", ".wmv", ".webm", ".mpg", ".mpeg", ".3gp", ".ts"}
    filename = file_stream.filename or "video.mp4"
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_VIDEO_EXT:
        return error_response(error="UploadError", message=f"不支持的视频格式: {ext}，支持: {', '.join(sorted(ALLOWED_VIDEO_EXT))}", code=400)

    try:
        content = await file_stream.read()
        result = service.upload_video_file_from_bytes(
            file_content=content,
            filename=filename
        )
        return success_response(data={"id": result["id"]}, message="上传成功", code=201)
    except (ValueError, IOError) as e:
        return error_response(error="UploadError", message=str(e), code=400)


@router.get("/random", summary="获取随机视频")
def get_random_video(
    video_type: Optional[int] = Query(None, description="视频类型"),
    service: VideoService = Depends(get_video_service)
):
    """获取随机视频"""
    video_data = service.get_random_video(video_type=video_type)
    if video_data:
        return success_response(data=video_data, message="获取成功")
    return error_response(error="NotFound", message="没有可用的视频", code=404)


# ==================== 视频下载 ====================

@router.post("/download", summary="下载视频")
async def download_video(
    req: VideoDownloadRequest,
    service: VideoService = Depends(get_video_service)
):
    """从URL下载视频"""
    try:
        logger.info("---------------------------------")
        result = service.download_video(req.video_url)
        return success_response(data=result, message="下载成功")
    except ValueError as e:
        return error_response(error="DownloadError", message=str(e), code=400)


# ==================== 视频处理 ====================

@router.post("/process", summary="处理视频")
async def process_video(
    req: VideoProcessRequest,
    service: VideoService = Depends(get_video_service)
):
    """处理视频（剪辑、变速、调整音量等）"""
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


@router.post("/extract-frame", summary="提取视频帧")
async def extract_frame(
    req: VideoExtractFrameRequest,
    service: VideoService = Depends(get_video_service)
):
    """提取视频帧为图片"""
    try:
        result = service.extract_frame(req.video_input, req.time_ss)
        return success_response(data=result, message="提取成功")
    except ValueError as e:
        return error_response(error="ExtractError", message=str(e), code=400)


@router.post("/extract-audio", summary="提取音频")
async def extract_audio(
    req: VideoExtractAudioRequest,
    service: VideoService = Depends(get_video_service)
):
    """从视频中提取音频"""
    try:
        result = service.extract_audio(req.video_url)
        return success_response(data=result, message="提取成功")
    except ValueError as e:
        return error_response(error="ExtractError", message=str(e), code=400)


@router.post("/add-audio", summary="添加音频")
async def add_audio(
    req: VideoAddAudioRequest,
    service: VideoService = Depends(get_video_service)
):
    """添加音频到视频"""
    try:
        result = service.add_audio_to_video(req.video_path, req.audio_path)
        return success_response(data=result, message="添加成功")
    except ValueError as e:
        return error_response(error="MergeError", message=str(e), code=400)


# ==================== 字幕相关 ====================

@router.post("/transcribe", summary="音视频转录")
async def transcribe(
    req: TranscribeRequest,
    service: VideoService = Depends(get_video_service)
):
    """音视频转录生成字幕"""
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


@router.post("/subtitle", summary="添加字幕")
async def add_subtitle(
    req: VideoAddSubtitleRequest,
    service: VideoService = Depends(get_video_service)
):
    """为视频添加字幕"""
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


# ==================== 批量操作 ====================

@router.post("/compress", summary="批量压缩")
def batch_compress(req: BatchCompressRequest):
    """启动批量视频压缩任务"""
    from src.shared.utils import file_util
    from src.application.services import ffmpeg_adapter as use_ffmpeg

    logger.info("启动批量视频压缩任务")
    use_ffmpeg.batch_compress_videos(
        input_dir=file_util.format_windows_path(req.input_dir),
        backup_dir=file_util.format_windows_path(req.backup_dir),
        crf=req.crf,
        max_bitrate=req.max_bitrate
    )
    return success_response(message="压缩任务已启动")


# ==================== 动态路由（必须放在所有静态路由之后） ====================

@router.get("/{video_id}", summary="获取视频详情")
def get_video(
    video_id: int = PathParam(..., description="视频ID"),
    service: VideoService = Depends(get_video_service)
):
    """获取视频详情"""
    video_data = service.get_video_by_id(video_id)
    if not video_data:
        return error_response(error="NotFound", message=f"视频 {video_id} 不存在", code=404)
    return success_response(data=video_data, message="获取成功")


@router.patch("/{video_id}", summary="更新视频信息")
def update_video(
    video_id: int = PathParam(..., description="视频ID"),
    req: VideoUpdateRequest = None,
    service: VideoService = Depends(get_video_service)
):
    """更新视频信息"""
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

    video_data = service.update_video(video_id, **update_data)
    if video_data:
        return success_response(data={"id": video_id}, message="更新成功")
    return error_response(error="NotFound", message=f"视频 {video_id} 不存在", code=404)


@router.delete("/{video_id}", summary="删除视频")
def delete_video(
    video_id: int = PathParam(..., description="视频ID"),
    service: VideoService = Depends(get_video_service)
):
    """删除视频"""
    try:
        service.delete_video(video_id)
        return success_response(data={"id": video_id}, message="删除成功")
    except FileNotFoundError as e:
        return error_response(error="NotFound", message=str(e), code=404)


@router.get("/{video_id}/description", summary="获取视频描述")
def get_video_description(
    video_id: int = PathParam(..., description="视频ID"),
    service: VideoService = Depends(get_video_service)
):
    """获取视频描述（通过 AI 分析）"""
    video_data = service.get_video_by_id(video_id)
    if not video_data:
        return error_response(error="NotFound", message=f"视频 {video_id} 不存在", code=404)

    try:
        from src.application.services.qwen_vl_adapter import video_summary
        description = video_summary(video_data.get("local_path"), None)
        # 清洗 LLM 返回的 markdown 代码块标记
        if description:
            description = description.strip()
            if description.startswith("```"):
                description = description.split("\n", 1)[-1]
            if description.endswith("```"):
                description = description[:-3]
            description = description.strip()
    except ImportError:
        logger.warning(f"video_summary 模块不可用，跳过描述生成")
        description = ""

    service.update_video_description(video_id, description)
    return success_response(data={"description": description}, message="获取描述成功")
