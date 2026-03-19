"""
语音服务 API 模块

提供语音相关的 API 接口，包括 TTS、音频处理、音色管理等功能
"""
from typing import Optional

from fastapi import APIRouter, UploadFile, Form, File, Depends, Query
from sqlalchemy.orm import Session

import config
from src.model.base import BaseReq, FishVoiceTTSReq
from src.model.response import success_response, error_response
from src.db.session import get_db
from src.service.audio_service import AudioService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


def get_audio_service(db: Session = Depends(get_db)) -> AudioService:
    """获取 AudioService 依赖"""
    return AudioService(db)


@router.post("/get_source_audio")
def get_source_audio(
    req: BaseReq = None,
    service: AudioService = Depends(get_audio_service)
):
    """获取音色列表（分页）"""
    # 如果请求体为空，使用默认值
    if req is None:
        req = BaseReq()

    logger.info(f"get_source_audio request: {req.model_dump()}")
    from src.util.pagination import PaginatedQuery

    page_params = PaginatedQuery(page=req.current, page_size=req.size)

    # 获取总数
    total = service.repository.count_active()
    logger.info(f"count_active result: {total}")

    # 获取数据
    items = service.repository.get_active_audios(skip=page_params.offset, limit=page_params.limit)
    logger.info(f"get_active_audios result: {len(items)} items")

    return success_response(
        data={
            "items": service.repository.bulk_to_dict(items, include_web_path=True),
            "total": total,
            "page": page_params.page,
            "page_size": page_params.page_size,
            "total_pages": (total + page_params.page_size - 1) // page_params.page_size
        },
        message="获取音色列表成功"
    )


@router.post("/del_source_audio")
def del_source_audio(
    req: BaseReq,
    service: AudioService = Depends(get_audio_service)
):
    """删除音色"""
    try:
        service.delete_audio(req.id)
        return success_response(data={"id": req.id}, message="删除成功")
    except FileNotFoundError as e:
        return error_response(error="NotFound", message=str(e), code=404)


@router.post("/save_timbre")
async def save_timbre(
    file: UploadFile = File(...),
    audio_name: str = Form(...),
    prompt_text: str = Form(...),
    seed: int = Form(...),
    speed: float = Form(...),
    top_p: float = Form(...),
    temperature: float = Form(...),
    repetition_penalty: float = Form(...),
    output_format: str = Form(...),
    service: AudioService = Depends(get_audio_service)
):
    """保存音色文件到数据库"""
    try:
        # 读取文件内容（异步读取）
        content = await file.read()

        result = service.save_timbre_from_bytes(
            file_content=content,
            filename=file.filename or "audio.wav",
            audio_name=audio_name,
            prompt_text=prompt_text,
            seed=seed,
            speed=speed,
            top_p=top_p,
            temperature=temperature,
            repetition_penalty=repetition_penalty,
            output_format=output_format
        )
        return success_response(data={"id": result["id"]}, message="保存音色成功")
    except (ValueError, IOError) as e:
        return error_response(error="SaveError", message=str(e), code=400)


@router.post("/sovits_v4")
async def tts_endpoint(req: BaseReq):
    """语音克隆（SoVITS V4）"""
    from src.db.session import get_db_context

    with get_db_context() as db:
        service = AudioService(db)
        try:
            req_dict = req.dict()

            result = service.generate_sovits_tts(
                text=req_dict.get("text", ""),
                ref_wav_path=req_dict.get("ref_wav_path", ""),
                prompt_text=req_dict.get("prompt_text", None),
                prompt_language=req_dict.get("prompt_language", None),
                text_language=req_dict.get("text_language", None),
                how_to_cut=req_dict.get("how_to_cut", None),
                top_k=req_dict.get("top_k", None),
                top_p=req_dict.get("top_p", None),
                temperature=req_dict.get("temperature", None),
                speed=req_dict.get("speed", None),
            )
            return success_response(data=result, message="语音生成成功")
        except ValueError as e:
            return error_response(error="TTSError", message=str(e), code=500)


@router.post("/separate_audio")
async def separate_audio(req: BaseReq):
    """分离音频和伴奏"""
    from src.db.session import get_db_context

    with get_db_context() as db:
        service = AudioService(db)
        try:
            result = service.separate_audio(req.audio_path)
            return success_response(data=result, message="分离成功")
        except ValueError as e:
            return error_response(error="SeparateError", message=str(e), code=500)


@router.post("/merge_audio")
async def merge_audio(req: BaseReq):
    """合并伴奏"""
    from src.db.session import get_db_context

    with get_db_context() as db:
        service = AudioService(db)
        try:
            result = service.merge_audio(
                source_audio_path=req.sourceAudioPath,
                accompaniment_url=req.accompanimentUrl
            )
            return success_response(data=result, message="合并成功")
        except ValueError as e:
            return error_response(error="MergeError", message=str(e), code=500)


@router.post("/fish_voice")
async def fish_voice_tts_endpoint(
    req: FishVoiceTTSReq,
    service: AudioService = Depends(get_audio_service)
):
    """生成语音（Fish Speech TTS）

    Args:
        req.text: 要合成的文本
        req.audio_source_id: 音色ID，-1表示使用自定义参考音频
        req.speed_factor: 语速因子 (1.0为正常语速)
        req.top_p: 采样概率阈值 (控制生成多样性)
        req.temperature: 温度参数 (控制随机性)
        req.repetition_penalty: 重复惩罚因子 (避免重复)
        req.references_audio: 参考音频(base64编码的音频字符串)
        req.references_text: 参考音频文本
    """
    try:
        result = service.generate_fish_speech_tts(
            text=req.text,
            audio_source_id=req.audio_source_id,
            seed=req.seed,
            speed_factor=req.speed_factor,
            top_p=req.top_p,
            temperature=req.temperature,
            repetition_penalty=req.repetition_penalty,
            references_audio=req.references_audio,
            references_text=req.references_text
        )
        return success_response(data=result, message="语音生成成功")
    except ValueError as e:
        return error_response(error="TTSError", message=str(e), code=500)
    except Exception as e:
        logger.error(f"语音生成失败: {e}")
        return error_response(error="TTSError", message=f"语音生成失败: {str(e)}", code=500)


@router.get("/get_random_audio")
def get_random_audio(
    service: AudioService = Depends(get_audio_service)
):
    """获取随机音色"""
    try:
        audio_obj = service.repository.get_random_active()
        if audio_obj:
            return success_response(data=service.repository.to_dict(audio_obj), message="获取成功")
        return error_response(error="NotFound", message="没有可用的音色", code=404)
    except Exception as e:
        logger.error(f"获取随机音色失败: {e}")
        return error_response(error="DatabaseError", message=f"获取失败: {str(e)}", code=500)
