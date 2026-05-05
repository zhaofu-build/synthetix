"""
视频 API 模块

提供视频相关的 RESTful API 接口，包括视频素材管理、视频处理、字幕等功能

路由前缀: /api/videos

注意：路由顺序很重要！静态路由必须在动态路由（/{video_id}）之前定义。
"""
import os
import json
import time
import logging
import tempfile
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
    include_temp: bool = Query(default=False, description="是否包含临时素材"),
    service: VideoService = Depends(get_video_service)
):
    """获取视频素材列表（分页，默认不含临时素材）"""
    result = service.get_paginated_videos(page=page, page_size=page_size, video_type=video_type, include_temp=include_temp)
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


# ==================== 在线搜索 ====================

@router.get("/search-online", summary="在线搜索视频素材")
def search_online(query: str = Query(..., description="搜索关键词"),
                  source: str = Query(default="all", description="来源: pexels/pixabay/all")):
    """搜索在线视频素材（Pexels + Pixabay）"""
    from src.application.services.video_downloader_adapter import search_videos
    try:
        results = search_videos(query, minimum_duration=3, source=source)
        return success_response(data={"videos": results})
    except Exception as e:
        logger.error(f"在线搜索失败: {e}")
        return error_response(error="SearchError", message=str(e), code=500)


# ==================== 视频下载 ====================

@router.post("/download", summary="下载视频")
async def download_video(
    req: VideoDownloadRequest,
    service: VideoService = Depends(get_video_service)
):
    """从URL下载视频"""
    try:
        logger.info("---------------------------------")
        result = service.download_video(req.video_url, tags=req.tags)
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
            subtitle_bottom=req.subtitle_bottom,
            fontbordercolor=req.fontbordercolor,
            bold=req.bold,
            outline_width=req.outline_width,
            shadow=req.shadow,
            alignment=req.alignment,
            bg_color=req.bg_color,
            margin_l=req.margin_l,
            margin_r=req.margin_r,
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
    if req.tags is not None:
        update_data['tags'] = req.tags

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
    print(f"[AI预处理] video_id={video_id}", flush=True)
    video_data = service.get_video_by_id(video_id)
    if not video_data:
        return error_response(error="NotFound", message=f"视频 {video_id} 不存在", code=404)

    local_path = video_data.get("local_path")
    if not local_path or not os.path.isfile(local_path):
        return error_response(error="FileNotFound", message="文件不存在，无法分析", code=400)

    ext = os.path.splitext(local_path)[1].lower()
    is_image = ext in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp'}
    is_audio = ext in {'.mp3', '.wav', '.aac', '.flac', '.m4a', '.ogg', '.wma'}
    is_video = not is_image and not is_audio

    # 1. VL 画面分析（图片和视频）
    vl_description = ""
    asr_skipped_reason = "纯音频文件" if is_audio else None
    if is_image:
        try:
            from src.application.services.qwen_vl_adapter import image_summary
            prompt = "各用一句话精简描述这张图片的核心内容（场景、主体、风格）。直接输出文本，不要输出JSON。"
            vl_description = image_summary(tmp_path=local_path, prompt=prompt)
            if vl_description:
                vl_description = vl_description.strip()
                if vl_description.startswith("```"):
                    vl_description = vl_description.split("\n", 1)[-1]
                if vl_description.endswith("```"):
                    vl_description = vl_description[:-3]
                vl_description = vl_description.strip()
        except Exception as e:
            print(f"[AI预处理] 图片VL失败: {e}", flush=True)
    elif is_video:
        # 获取视频时长
        duration = None
        try:
            from src.application.services import ffmpeg_adapter as ffmpeg
            info = ffmpeg.get_video_info(local_path) or {}
            duration = float(info.get("duration", 0)) if info.get("duration") else None
        except Exception:
            pass

        try:
            from src.application.services.qwen_vl_adapter import video_summary
            prompt = (
                "请分析这个视频，按时间顺序描述每个连续画面片段的内容。" +
                (f"\n重要：该视频总时长为 {duration:.1f}秒，所有片段的end时间不得超过 {duration:.1f}。" if duration else "") +
                "\n要求：\n"
                "1. start和end必须是视频的真实秒数，严格对齐视频实际时长\n"
                "2. 所有片段时间必须连续且覆盖完整时长\n"
                "3. desc简述该时间段的真实画面内容，包括场景、人物动作、文字、风格等\n"
                "4. 严格按以下JSON格式输出，不要输出任何其他文字：\n"
                '{"segments":[{"start":0,"end":5,"desc":"画面描述"},{"start":5,"end":12,"desc":"画面描述"}]}'
            )
            vl_description = video_summary(local_path, prompt, duration=duration)
            if vl_description:
                vl_description = vl_description.strip()
                if vl_description.startswith("```"):
                    vl_description = vl_description.split("\n", 1)[-1]
                if vl_description.endswith("```"):
                    vl_description = vl_description[:-3]
                vl_description = vl_description.strip()
        except Exception as e:
            print(f"[AI预处理] VL失败: {e}", flush=True)

    # 2. ASR 字幕提取（视频和音频文件）
    subtitle = ""
    if is_video or is_audio:
        if not asr_skipped_reason:
            asr_skipped_reason = None
        try:
            from src.application.services import whisper_adapter, ffmpeg_adapter
            asr_input = local_path
            # 视频文件需要提取音频为 MP3；音频文件直接使用
            if is_video:
                audio_tmp = os.path.join(tempfile.gettempdir(), f"synthetix_asr_{video_id}_{int(time.time())}.mp3")
                try:
                    ffmpeg_adapter.run_ffmpeg_cmd([
                        '-y', '-i', local_path,
                        '-vn', '-acodec', 'libmp3lame', '-q:a', '9',
                        audio_tmp
                    ])
                    if os.path.exists(audio_tmp) and os.path.getsize(audio_tmp) > 0:
                        asr_input = audio_tmp
                    else:
                        asr_skipped_reason = "无音轨"
                        asr_input = None
                except Exception:
                    asr_skipped_reason = "无音轨"
                    asr_input = None
            # 音频文件：如果是 WAV/FLAC 等大文件，转为 MP3 压缩
            elif is_audio and ext in ('.wav', '.flac'):
                audio_tmp = os.path.join(tempfile.gettempdir(), f"synthetix_asr_{video_id}_{int(time.time())}.mp3")
                try:
                    ffmpeg_adapter.run_ffmpeg_cmd([
                        '-y', '-i', local_path,
                        '-acodec', 'libmp3lame', '-q:a', '9',
                        audio_tmp
                    ])
                    if os.path.exists(audio_tmp) and os.path.getsize(audio_tmp) > 0:
                        asr_input = audio_tmp
                except Exception:
                    pass  # 回退用原文件
            if asr_input:
                subtitle = whisper_adapter.transcribe(asr_input, output_format_type="srt", subtitle_language="zh")
                if asr_input != local_path and os.path.exists(asr_input):
                    try:
                        os.remove(asr_input)
                    except OSError:
                        pass
        except Exception as e:
            print(f"[AI预处理] ASR失败: {e}", flush=True)
            if not asr_skipped_reason:
                asr_skipped_reason = f"提取失败: {e}"

    # 3. 合并存储
    if is_image:
        # 图片直接存纯文本描述
        description = vl_description or ""
        if not description:
            return error_response(error="AnalysisFailed", message="AI 分析失败：图片描述生成未返回结果", code=500)
    else:
        # 视频/音频存结构化 JSON
        combined = {}
        if vl_description:
            try:
                parsed = json.loads(vl_description)
                if isinstance(parsed, dict) and "segments" in parsed:
                    combined["segments"] = parsed["segments"]
                else:
                    combined["vl_text"] = vl_description
            except (json.JSONDecodeError, ValueError):
                combined["vl_text"] = vl_description
        if subtitle:
            combined["transcription"] = subtitle
        elif asr_skipped_reason:
            combined["transcription"] = ""
        if asr_skipped_reason:
            combined["asr_status"] = asr_skipped_reason

        if not combined:
            return error_response(error="AnalysisFailed", message="AI 分析失败：VL 画面分析和 ASR 字幕提取均未返回结果，请检查 AI 服务配置", code=500)
        description = json.dumps(combined, ensure_ascii=False)

    service.update_video_description(video_id, description)
    return success_response(data={"description": description}, message="分析完成")
