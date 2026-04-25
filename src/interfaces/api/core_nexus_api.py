"""
Core-Nexus-AI 代理 API

代理 LLM、TTS、ASR、VL 接口到前端
"""
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
    """VL 请求"""
    prompt: str
    image: Optional[str] = None
    images: Optional[List[str]] = None
    messages: Optional[List[Dict[str, Any]]] = None
    generation: Optional[Dict[str, Any]] = None


# ==================== 模型列表接口 ====================

@router.get("/models", summary="获取可用模型列表")
async def list_models(
    task_type: Optional[str] = Query(default=None, description="任务类型: LLM/TTS/ASR/VL/TEXT_TO_MUSIC"),
    base_url: Optional[str] = Query(default=None, description="服务地址（可选，未传则用已保存配置）"),
):
    """代理 core-nexus-ai 的 /api/models 接口"""
    url = base_url or cfg_get("core_nexus.base_url") or config.CORE_NEXUS_BASE_URL
    if not url:
        return success_response(data=[], message="CORE_NEXUS_BASE_URL 未配置")
    url = url.strip().rstrip('/')

    try:
        params = {}
        if task_type:
            params["task_type"] = task_type

        async with httpx.AsyncClient(timeout=10.0) as http_client:
            resp = await http_client.get(f"{url}/api/models", params=params)
            resp.raise_for_status()
            data = resp.json()

        return success_response(data=data, to_camel=False)
    except Exception as e:
        logger.error(f"获取模型列表失败: {e}")
        return error_response(error="ModelListError", message=str(e), code=500)


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
        return error_response(error="ConnectionError", message=f"连接失败 ({test_url}): {e}", code=500)


# ==================== LLM 接口 ====================

@router.post("/llm")
async def llm_generate(request: LLMRequest):
    """
    LLM 文本生成

    支持 prompt 单轮对话或 messages 多轮对话
    """
    try:
        client = get_client()

        # 构建 messages
        if request.messages:
            messages = request.messages
        elif request.prompt:
            messages = [{"role": "user", "content": request.prompt}]
        else:
            return error_response(error="BadRequest", message="需要提供 prompt 或 messages", code=400)

        # 生成参数
        gen_config = request.generation or GenerationConfig()

        result = await client.llm_generate_async(
            messages=messages,
            model=request.model,
            temperature=gen_config.temperature,
            max_tokens=gen_config.max_tokens
        )

        return success_response(data={"text": result})

    except Exception as e:
        logger.error(f"LLM 生成失败: {e}", exc_info=True)
        return error_response(error="LLMError", message=str(e), code=500)


@router.post("/llm/stream")
async def llm_generate_stream(request: LLMRequest):
    """
    LLM 流式文本生成

    返回 SSE 流
    """
    try:
        client = get_client()

        # 构建 messages
        if request.messages:
            messages = request.messages
        elif request.prompt:
            messages = [{"role": "user", "content": request.prompt}]
        else:
            return error_response(error="BadRequest", message="需要提供 prompt 或 messages", code=400)

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

    except Exception as e:
        logger.error(f"LLM 流式生成失败: {e}", exc_info=True)
        return error_response(error="LLMError", message=str(e), code=500)


# ==================== TTS 接口 ====================

@router.post("/tts")
async def tts_generate(request: TTSRequest):
    """
    TTS 文本转语音

    返回音频文件
    """
    try:
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

    except Exception as e:
        logger.error(f"TTS 生成失败: {e}", exc_info=True)
        return error_response(error="TTSError", message=str(e), code=500)


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
    try:
        client = get_client()

        # 处理上传的参考音频
        ref_audio_data = None
        if ref_audio:
            audio_bytes = await ref_audio.read()
            ref_audio_data = base64.b64encode(audio_bytes).decode('utf-8')

        audio_data = await client.tts_generate_async(
            text=text,
            speaker=speaker,
            ref_audio=ref_audio_data,
            ref_text=ref_text,
            language=language,
        )

        return Response(
            content=audio_data,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=tts_output.wav"
            }
        )

    except Exception as e:
        logger.error(f"TTS 生成失败: {e}", exc_info=True)
        return error_response(error="TTSError", message=str(e), code=500)


# ==================== ASR 接口 ====================

@router.post("/asr")
async def asr_transcribe(request: ASRRequest):
    """
    ASR 语音识别

    接收 base64 音频数据
    """
    try:
        client = get_client()

        result = await client.asr_transcribe_async(
            audio=request.audio,
            language=request.language,
            **(request.generation or {})
        )

        return success_response(data=result)

    except Exception as e:
        logger.error(f"ASR 识别失败: {e}", exc_info=True)
        return error_response(error="ASRError", message=str(e), code=500)


@router.post("/asr/upload")
async def asr_with_upload(
    audio: UploadFile = File(...),
    language: Optional[str] = Form(None),
):
    """
    ASR 语音识别（上传文件）

    支持上传音频文件进行识别
    """
    try:
        client = get_client()

        # 读取上传的音频文件
        audio_bytes = await audio.read()
        audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

        result = await client.asr_transcribe_async(
            audio=audio_base64,
            language=language,
        )

        return success_response(data=result)

    except Exception as e:
        logger.error(f"ASR 识别失败: {e}", exc_info=True)
        return error_response(error="ASRError", message=str(e), code=500)


# ==================== VL 接口 ====================

@router.post("/vl")
async def vl_generate(request: VLRequest):
    """
    VL 视觉语言理解

    支持单图或多图输入
    """
    try:
        client = get_client()

        result = await client.vl_generate_async(
            prompt=request.prompt,
            image=request.image,
            images=request.images,
            messages=request.messages,
            **(request.generation or {})
        )

        return success_response(data={"text": result})

    except Exception as e:
        logger.error(f"VL 生成失败: {e}", exc_info=True)
        return error_response(error="VLError", message=str(e), code=500)


@router.post("/vl/stream")
async def vl_generate_stream(request: VLRequest):
    """
    VL 流式视觉语言理解

    返回 SSE 流
    """
    try:
        client = get_client()

        async def generate():
            try:
                async for chunk in client.vl_generate_stream_async(
                    prompt=request.prompt,
                    image=request.image,
                    images=request.images,
                    messages=request.messages,
                    **(request.generation or {})
                ):
                    yield f"data: {json.dumps({'text': chunk}, ensure_ascii=False)}\n\n"
                yield "data: [DONE]\n\n"
            except Exception as e:
                logger.error(f"VL 流式生成失败: {e}", exc_info=True)
                yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        return StreamingResponse(
            generate(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            }
        )

    except Exception as e:
        logger.error(f"VL 流式生成失败: {e}", exc_info=True)
        return error_response(error="VLError", message=str(e), code=500)


@router.post("/vl/upload")
async def vl_with_upload(
    prompt: str = Form(...),
    image: Optional[UploadFile] = File(None),
):
    """
    VL 视觉语言理解（上传图片）

    支持上传图片进行分析
    """
    try:
        client = get_client()

        # 处理上传的图片
        image_data = None
        if image:
            image_bytes = await image.read()
            image_data = base64.b64encode(image_bytes).decode('utf-8')

        result = await client.vl_generate_async(
            prompt=prompt,
            image=image_data,
        )

        return success_response(data={"text": result})

    except Exception as e:
        logger.error(f"VL 生成失败: {e}", exc_info=True)
        return error_response(error="VLError", message=str(e), code=500)


# ==================== Music 接口 ====================

class TextToMusicRequest(BaseModel):
    """文本生成音乐请求"""
    prompt: str
    duration: Optional[float] = 10.0
    style: Optional[str] = None
    model: Optional[str] = None
    generation: Optional[Dict[str, Any]] = None


@router.post("/music")
async def text_to_music(request: TextToMusicRequest):
    """
    文本生成音乐

    根据文本描述生成音乐，支持指定风格和时长
    """
    try:
        client = get_client()

        result = await client.text_to_music_async(
            prompt=request.prompt,
            duration=request.duration,
            style=request.style,
            model=request.model,
            **(request.generation or {})
        )

        # 返回音频数据
        audio_data = result.get("audio", "")
        if audio_data.startswith("data:"):
            # 移除 data URL 前缀
            audio_data = audio_data.split(",", 1)[1]
            audio_bytes = base64.b64decode(audio_data)
        else:
            audio_bytes = base64.b64decode(audio_data)

        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": "attachment; filename=music_output.wav"
            }
        )

    except Exception as e:
        logger.error(f"音乐生成失败: {e}", exc_info=True)
        return error_response(error="MusicError", message=str(e), code=500)
