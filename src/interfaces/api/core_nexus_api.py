"""
Core-Nexus-AI 代理 API

代理 LLM、TTS、ASR、Multimodal 接口到前端
"""
import os
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
import json
import base64
import httpx

from src.shared.utils.core_nexus_client import get_client
from src.shared.models.response import success_response, error_response
from src.shared.exceptions.exceptions import ValidationException, ResourceNotFoundException, ExternalServiceException
from src.shared.utils.config_manager import get as cfg_get
from src import config

logger = logging.getLogger(__name__)
router = APIRouter()


# ==================== 请求模型 ====================

class GenerationConfig(BaseModel):
    """生成配置"""
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 2048


class LLMRequest(BaseModel):
    """LLM 请求"""
    prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    model: Optional[str] = None
    generation: Optional[GenerationConfig] = None


class TTSRequest(BaseModel):
    """TTS 请求"""
    text: str
    model: Optional[str] = None
    speaker: Optional[str] = None
    ref_audio: Optional[str] = None
    ref_text: Optional[str] = None
    language: Optional[str] = "Auto"
    instruct: Optional[str] = None
    generation: Optional[Dict[str, Any]] = None


class ASRRequest(BaseModel):
    """ASR 请求"""
    audio: str
    language: Optional[str] = None
    generation: Optional[Dict[str, Any]] = None


class VLRequest(BaseModel):
    """VL 请求（兼容旧前端）"""
    prompt: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    generation: Optional[Dict[str, Any]] = None


class MultimodalRequest(BaseModel):
    """Multimodal 多模态请求"""
    prompt: Optional[str] = None
    image: Optional[str] = None
    images: Optional[List[str]] = None
    video: Optional[str] = None
    videos: Optional[List[str]] = None
    video_frames: Optional[List[str]] = None
    audio: Optional[str] = None
    audios: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    modalities: Optional[List[str]] = None
    voice: Optional[str] = None
    audio_format: Optional[str] = None
    enable_thinking: Optional[bool] = None
    enable_search: Optional[bool] = None
    model: Optional[str] = None
    generation: Optional[Dict[str, Any]] = None


# ==================== 模型列表接口 ====================

@router.get("/models", summary="获取可用模型列表")
async def list_models(
    task_type: Optional[str] = Query(default=None, description="任务类型: LLM/TTS/ASR/MULTIMODAL/VIDEO_GEN/TEXT_TO_MUSIC/TEXT_TO_IMAGE"),
    base_url: Optional[str] = Query(default=None, description="服务地址（可选，未传则用已保存配置）"),
):
    """代理 core-nexus-ai 的 /api/models 接口"""
    url = base_url or cfg_get("core_nexus.base_url") or config.CORE_NEXUS_BASE_URL
    if not url:
        return success_response(data=[], message="CORE_NEXUS_BASE_URL 未配置")
    url = url.strip().rstrip('/')

    # 读取 API Key
    api_key = cfg_get("core_nexus.api_key") or getattr(config, "LLM_KEY", "")

    try:
        params = {}
        if task_type:
            params["task_type"] = task_type

        headers = {}
        if api_key:
            headers["X-API-Key"] = api_key

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(f"{url}/api/models", params=params, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        return success_response(data=data, to_camel=False)
    except Exception as e:
        raise ExternalServiceException(service_name="CoreNexus", message="获取模型列表失败，请检查服务配置")


class TestConnectionRequest(BaseModel):
    """测试连接请求"""
    base_url: str


@router.post("/test-connection", summary="测试 core-nexus-ai 连接")
async def test_connection(req: TestConnectionRequest):
    """测试 core-nexus-ai 连接是否正常"""
    base_url = req.base_url.strip().rstrip('/')
    if not base_url:
        return error_response(error="ConfigError", message="请输入服务地址", code=400)

    test_url = f"{base_url}/health"
    try:
        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(test_url)
            resp.raise_for_status()
        return success_response(data={"status": "ok", "tested_url": test_url}, message="连接成功")
    except Exception as e:
        raise ExternalServiceException(service_name="CoreNexus", message="连接测试失败，请检查服务地址和密钥")


# ==================== LLM 接口 ====================

@router.post("/llm")
async def llm_generate(request: LLMRequest):
    """
    LLM 文本生成

    支持 prompt 单轮对话或 messages 多轮对话
    """
    client = get_client()

    # 构建 messages
    if request.messages:
        messages = request.messages
    elif request.prompt:
        messages = [{"role": "user", "content": request.prompt}]
    else:
        raise ValidationException("需要提供 prompt 或 messages")

    # 生成参数
    gen_config = request.generation or GenerationConfig()

    result = await client.llm_generate_async(
        messages=messages,
        model=request.model,
        temperature=gen_config.temperature,
        max_tokens=gen_config.max_tokens
    )

    return success_response(data={"text": result})


@router.post("/llm/stream")
async def llm_generate_stream(request: LLMRequest):
    """
    LLM 流式文本生成

    返回 SSE 流
    """
    client = get_client()

    # 构建 messages
    if request.messages:
        messages = request.messages
    elif request.prompt:
        messages = [{"role": "user", "content": request.prompt}]
    else:
        raise ValidationException("需要提供 prompt 或 messages")

    # 生成参数
    gen_config = request.generation or GenerationConfig()

    async def generate():
        try:
            async for chunk in client.llm_generate_stream_async(
                messages=messages,
                model=request.model,
                temperature=gen_config.temperature,
                max_tokens=gen_config.max_tokens
            ):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"LLM 流式生成失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ==================== TTS 接口 ====================

@router.post("/tts")
async def tts_generate(request: TTSRequest):
    """
    TTS 文本转语音

    返回音频文件
    """
    client = get_client()

    audio_data = await client.tts_generate_async(
        text=request.text,
        model=request.model,
        speaker=request.speaker,
        ref_audio=request.ref_audio,
        ref_text=request.ref_text,
        language=request.language,
        instruct=request.instruct,
        generation=request.generation
    )

    return Response(
        content=audio_data,
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=tts_output.wav"
        }
    )


@router.post("/tts/upload")
async def tts_with_upload(
    text: str = Form(...),
    speaker: Optional[str] = Form(None),
    language: Optional[str] = Form("Auto"),
    ref_audio: Optional[UploadFile] = File(None),
    ref_text: Optional[str] = Form(None),
):
    """
    TTS 文本转语音（支持上传参考音频）

    用于语音克隆场景
    """
    client = get_client()

    # 处理上传的参考音频
    ref_audio_data = None
    if ref_audio:
        audio_bytes = await ref_audio.read()
        if len(audio_bytes) > 20 * 1024 * 1024:  # 20MB
            raise ValidationException("参考音频文件不能超过 20MB")
        ref_audio_data = base64.b64encode(audio_bytes).decode('utf-8')

    audio_data = await client.tts_generate_async(
        text=text,
        speaker=speaker,
        ref_audio=ref_audio_data,
        ref_text=ref_text,
        language=language,
        model=cfg_get("core_nexus.tts_model") or None,
    )

    return Response(
        content=audio_data,
        media_type="audio/wav",
        headers={
            "Content-Disposition": "attachment; filename=tts_output.wav"
        }
    )


# ==================== ASR 接口 ====================

@router.post("/asr")
async def asr_transcribe(request: ASRRequest):
    """
    ASR 语音识别

    接收 base64 音频数据
    """
    client = get_client()

    result = await client.asr_transcribe_async(
        audio=request.audio,
        language=request.language,
        model=cfg_get("core_nexus.asr_model") or None,
        **(request.generation or {})
    )

    return success_response(data=result)


@router.post("/asr/upload")
async def asr_with_upload(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
):
    """
    ASR 语音识别（上传文件）

    支持上传音频文件进行识别
    """
    client = get_client()

    # 读取上传的音频文件
    audio_bytes = await audio.read()
    if len(audio_bytes) > 20 * 1024 * 1024:  # 20MB
        raise ValidationException("音频文件不能超过 20MB")
    audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

    result = await client.asr_transcribe_async(
        audio=audio_base64,
        language=language,
        model=cfg_get("core_nexus.asr_model") or None,
    )

    return success_response(data=result)


# ==================== Multimodal 接口（原 VL，已合并为统一多模态） ====================

@router.post("/multimodal")
async def multimodal_generate(request: MultimodalRequest):
    """
    多模态推理

    支持文本+图像+音频+视频组合输入
    """
    client = get_client()

    result = await client.multimodal_generate_async(
        prompt=request.prompt,
        image=request.image,
        images=request.images,
        video=request.video,
        videos=request.videos,
        video_frames=request.video_frames,
        audio=request.audio,
        audios=request.audios,
        messages=request.messages,
        modalities=request.modalities,
        voice=request.voice,
        audio_format=request.audio_format,
        enable_thinking=request.enable_thinking,
        enable_search=request.enable_search,
        model=request.model or cfg_get("core_nexus.multimodal_model") or None,
        **(request.generation or {})
    )

    return success_response(data={"text": result})


@router.post("/multimodal/stream")
async def multimodal_generate_stream(request: MultimodalRequest):
    """
    多模态流式推理

    返回 SSE 流
    """
    client = get_client()

    async def generate():
        try:
            async for chunk in client.multimodal_generate_stream_async(
                prompt=request.prompt,
                image=request.image,
                images=request.images,
                video=request.video,
                videos=request.videos,
                video_frames=request.video_frames,
                audio=request.audio,
                audios=request.audios,
                messages=request.messages,
                modalities=request.modalities,
                voice=request.voice,
                audio_format=request.audio_format,
                enable_thinking=request.enable_thinking,
                enable_search=request.enable_search,
                model=request.model or cfg_get("core_nexus.multimodal_model") or None,
                **(request.generation or {})
            ):
                yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            logger.error(f"Multimodal 流式生成失败: {e}", exc_info=True)
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


@router.post("/multimodal/upload")
async def multimodal_with_upload(
    prompt: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    """
    多模态推理（上传图片）

    支持上传图片进行分析
    """
    client = get_client()

    # 处理上传的图片
    image_data = None
    if image:
        image_bytes = await image.read()
        if len(image_bytes) > 10 * 1024 * 1024:  # 10MB
            raise ValidationException("图片文件不能超过 10MB")
        image_data = base64.b64encode(image_bytes).decode('utf-8')

    result = await client.multimodal_generate_async(
        prompt=prompt,
        image=image_data,
        model=cfg_get("core_nexus.multimodal_model") or None,
    )

    return success_response(data={"text": result})


# 兼容旧前端路由
@router.post("/vl")
async def vl_generate_compat(request: VLRequest):
    """VL 兼容路由（转发到 multimodal）"""
    client = get_client()
    result = await client.multimodal_generate_async(
        prompt=request.prompt,
        image=request.image,
        images=request.images,
        messages=request.messages,
        model=cfg_get("core_nexus.multimodal_model") or None,
        **(request.generation or {})
    )
    return success_response(data={"text": result})


@router.post("/vl/upload")
async def vl_upload_compat(
    prompt: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    """VL 上传兼容路由"""
    client = get_client()
    image_data = None
    if image:
        image_bytes = await image.read()
        if len(image_bytes) > 10 * 1024 * 1024:
            raise ValidationException("图片文件不能超过 10MB")
        image_data = base64.b64encode(image_bytes).decode('utf-8')

    result = await client.multimodal_generate_async(
        prompt=prompt,
        image=image_data,
        model=cfg_get("core_nexus.multimodal_model") or None,
    )
    return success_response(data={"text": result})


# ==================== Music 接口 ====================

class TextToMusicRequest(BaseModel):
    """文本生成音乐请求"""
    prompt: str
    duration: Optional[float] = 10.0
    style: Optional[str] = None
    model: Optional[str] = None
    mode: Optional[str] = None
    lyrics: Optional[str] = None
    audio: Optional[str] = None
    variance: Optional[float] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    extend_left: Optional[float] = None
    extend_right: Optional[float] = None
    generation: Optional[Dict[str, Any]] = None


class MusicToMusicRequest(BaseModel):
    """音乐风格迁移请求"""
    audio: str
    prompt: Optional[str] = None
    style: Optional[str] = None
    model: Optional[str] = None
    generation: Optional[Dict[str, Any]] = None


def _decode_audio_response(result: dict) -> bytes:
    """从 API 结果中提取音频字节"""
    audio_data = result.get("audio", "")
    if audio_data.startswith("data:"):
        audio_data = audio_data.split(",", 1)[1]
    return base64.b64decode(audio_data)


@router.post("/music")
async def text_to_music(request: TextToMusicRequest):
    """
    文本生成音乐

    支持 generate/retake/repaint/edit/extend/cover 模式
    """
    client = get_client()

    result = await client.text_to_music_async(
        prompt=request.prompt,
        duration=request.duration,
        style=request.style,
        model=request.model,
        mode=request.mode,
        lyrics=request.lyrics,
        audio=request.audio,
        variance=request.variance,
        start_time=request.start_time,
        end_time=request.end_time,
        extend_left=request.extend_left,
        extend_right=request.extend_right,
        **(request.generation or {})
    )

    audio_bytes = _decode_audio_response(result)
    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=music_output.wav"}
    )


@router.post("/music-to-music")
async def music_to_music(request: MusicToMusicRequest):
    """音乐风格迁移"""
    client = get_client()
    result = await client.music_to_music_async(
        audio=request.audio,
        prompt=request.prompt,
        style=request.style,
        model=request.model,
        **(request.generation or {})
    )
    audio_bytes = _decode_audio_response(result)
    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Content-Disposition": "attachment; filename=style_transfer.wav"}
    )


@router.get("/music/bgm-audio/{bgm_id}")
async def get_bgm_audio(bgm_id: int):
    """获取 BGM 的 base64 音频数据（供前端音乐编辑模式使用）"""
    from src.infrastructure.db.session import get_db_context
    from src.domain.entities.bgm_item import BGMItem

    with get_db_context() as db:
        bgm = db.query(BGMItem).filter(BGMItem.id == bgm_id).first()
        if not bgm:
            raise ResourceNotFoundException(resource_type="BGMItem", resource_id=bgm_id)
        bgm_data = bgm.to_dict()
        local_path = bgm.local_path

    if not local_path or not os.path.exists(local_path):
        raise ResourceNotFoundException(resource_type="BGMFile", resource_id=bgm_id)

    with open(local_path, "rb") as f:
        audio_b64 = base64.b64encode(f.read()).decode("utf-8")

    return success_response(data={"audio": audio_b64, "bgm": bgm_data})
