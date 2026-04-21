"""
core-nexus-ai API 客户端

统一的 HTTP 客户端，用于调用 core-nexus-ai 服务
支持同步和异步两种调用方式
"""
import asyncio
import base64
import logging
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator, AsyncGenerator
import httpx

from src import config

logger = logging.getLogger(__name__)


class CoreNexusClient:
    """core-nexus-ai API 客户端"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        """
        初始化客户端

        Args:
            base_url: API 基础地址，默认从配置读取
            timeout: 请求超时时间（秒）
        """
        raw = (base_url or config.CORE_NEXUS_BASE_URL).strip()
        if raw and not raw.startswith(('http://', 'https://')):
            raw = f'http://{raw}'
        self.base_url = raw.rstrip('/')
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("CORE_NEXUS_BASE_URL 未配置，请在 .env 中设置")

        # 同步客户端（向后兼容）
        self._client = httpx.Client(timeout=timeout)
        # 异步客户端（懒加载）
        self._async_client: Optional[httpx.AsyncClient] = None
        logger.info(f"CoreNexusClient 初始化 | base_url: {self.base_url}")

    def close(self):
        """关闭同步客户端连接"""
        if hasattr(self, '_client') and self._client:
            self._client.close()

    async def close_async(self):
        """关闭异步客户端连接"""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None

    # ==================== 同步请求方法 ====================

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求（带指数退避重试）

        Args:
            method: HTTP 方法
            endpoint: API 端点
            json_data: JSON 请求数据
            max_retries: 最大重试次数
            **kwargs: 其他请求参数

        Returns:
            响应 JSON 数据

        Raises:
            httpx.HTTPError: HTTP 请求错误
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"API 请求: {method} {url}")

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._client.request(method, url, json=json_data, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.TransportError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 0.5 * (2 ** attempt)  # 0.5s, 1s, 2s
                    logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                    time.sleep(wait)
            except httpx.HTTPStatusError as e:
                # 4xx 客户端错误不重试
                if e.response.status_code < 500:
                    raise
                last_error = e
                if attempt < max_retries - 1:
                    wait = 0.5 * (2 ** attempt)
                    logger.warning(f"服务端错误 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                    time.sleep(wait)

        raise last_error

    def _request_stream(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        **kwargs
    ) -> Generator[Dict, None, None]:
        """
        发送 SSE 流式请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            json_data: JSON 请求数据
            **kwargs: 其他请求参数

        Yields:
            流式响应数据
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"API 流式请求: {method} {url}")

        with self._client.stream(method, url, json=json_data, **kwargs) as response:
            response.raise_for_status()
            for line in response.iter_lines():
                if line.startswith('data: '):
                    data = line[6:]  # 去掉 'data: ' 前缀
                    if data == '[DONE]':
                        break
                    import json
                    yield json.loads(data)

    # ==================== 异步请求方法 ====================

    async def _get_async_client(self) -> httpx.AsyncClient:
        """获取异步客户端（懒加载）"""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.timeout)
        return self._async_client

    async def _request_async(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        """
        异步发送 HTTP 请求（带指数退避重试）

        Args:
            method: HTTP 方法
            endpoint: API 端点
            json_data: JSON 请求数据
            max_retries: 最大重试次数
            **kwargs: 其他请求参数

        Returns:
            响应 JSON 数据
        """
        client = await self._get_async_client()
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"异步 API 请求: {method} {url}")

        last_error = None
        for attempt in range(max_retries):
            try:
                response = await client.request(method, url, json=json_data, **kwargs)
                response.raise_for_status()
                return response.json()
            except httpx.TransportError as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait = 0.5 * (2 ** attempt)
                    logger.warning(f"异步请求失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                    await asyncio.sleep(wait)
            except httpx.HTTPStatusError as e:
                if e.response.status_code < 500:
                    raise
                last_error = e
                if attempt < max_retries - 1:
                    wait = 0.5 * (2 ** attempt)
                    logger.warning(f"异步服务端错误 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                    await asyncio.sleep(wait)

        raise last_error

    async def _request_stream_async(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        **kwargs
    ) -> AsyncGenerator[Dict, None]:
        """
        异步 SSE 流式请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            json_data: JSON 请求数据
            **kwargs: 其他请求参数

        Yields:
            流式响应数据
        """
        client = await self._get_async_client()
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"异步 API 流式请求: {method} {url}")

        import json
        async with client.stream(method, url, json=json_data, **kwargs) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith('data: '):
                    data = line[6:]
                    if data == '[DONE]':
                        break
                    yield json.loads(data)

    # ==================== LLM 接口 ====================

    def llm_generate(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **generation_params
    ) -> str:
        """
        LLM 文本生成

        Args:
            messages: 对话消息列表
            model: 模型名称（可选，使用默认模型）
            temperature: 温度参数
            max_tokens: 最大 token 数
            **generation_params: 其他生成参数

        Returns:
            生成的文本
        """
        payload = {
            "messages": messages,
            "generation": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **generation_params
            }
        }
        if model:
            payload["model"] = model

        response = self._request('POST', '/llm', json_data=payload)
        return response.get('output', {}).get('text', '')

    async def llm_generate_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **generation_params
    ) -> str:
        """LLM 异步文本生成"""
        payload = {
            "messages": messages,
            "generation": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **generation_params
            }
        }
        if model:
            payload["model"] = model

        response = await self._request_async('POST', '/llm', json_data=payload)
        return response.get('output', {}).get('text', '')

    def llm_generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **generation_params
    ) -> Generator[str, None, None]:
        """
        LLM 流式文本生成
        """
        payload = {
            "messages": messages,
            "generation": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **generation_params
            }
        }
        if model:
            payload["model"] = model

        for chunk in self._request_stream('POST', '/llm/stream', json_data=payload):
            if 'text' in chunk:
                yield chunk['text']

    async def llm_generate_stream_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        **generation_params
    ) -> AsyncGenerator[str, None]:
        """LLM 异步流式文本生成"""
        payload = {
            "messages": messages,
            "generation": {
                "temperature": temperature,
                "max_tokens": max_tokens,
                **generation_params
            }
        }
        if model:
            payload["model"] = model

        async for chunk in self._request_stream_async('POST', '/llm/stream', json_data=payload):
            if 'text' in chunk:
                yield chunk['text']

    # ==================== ASR 接口 ====================

    def asr_transcribe(
        self,
        audio: str,
        language: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """ASR 语音识别"""
        audio_data = self._process_audio_input(audio)

        payload = {"audio": audio_data}
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/asr', json_data=payload)
        return response.get('output', {})

    async def asr_transcribe_async(
        self,
        audio: str,
        language: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """ASR 异步语音识别"""
        audio_data = self._process_audio_input(audio)

        payload = {"audio": audio_data}
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/asr', json_data=payload)
        return response.get('output', {})

    # ==================== TTS 接口 ====================

    def tts_generate(
        self,
        text: str,
        model: Optional[str] = None,
        speaker: Optional[str] = None,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: Optional[str] = "Auto",
        instruct: Optional[str] = None,
        generation: Optional[Dict] = None,
    ) -> bytes:
        """TTS 文本转语音"""
        payload = {"text": text}

        if ref_audio:
            payload["ref_audio"] = self._process_audio_input(ref_audio)
        if ref_text:
            payload["ref_text"] = ref_text
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        if speaker:
            payload["speaker"] = speaker
        if instruct:
            payload["instruct"] = instruct
        if generation:
            payload["generation"] = generation

        import json
        logger.info(f"TTS API 调用: POST {self.base_url}/tts")
        logger.info(f"TTS 完整请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        url = f"{self.base_url}/tts"
        response = self._client.post(url, json=payload, timeout=self.timeout)

        logger.debug(f"TTS 响应状态: {response.status_code}")

        if response.status_code >= 400:
            logger.error(f"TTS 错误响应: {response.text[:500]}")

        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            data = response.json()
            audio_data = data.get('output', {}).get('audio', '')
            if audio_data.startswith('data:'):
                audio_data = audio_data.split(',', 1)[1]
            return base64.b64decode(audio_data)

        return response.content

    async def tts_generate_async(
        self,
        text: str,
        model: Optional[str] = None,
        speaker: Optional[str] = None,
        ref_audio: Optional[str] = None,
        ref_text: Optional[str] = None,
        language: Optional[str] = "Auto",
        instruct: Optional[str] = None,
        generation: Optional[Dict] = None,
    ) -> bytes:
        """TTS 异步文本转语音"""
        payload = {"text": text}

        if ref_audio:
            payload["ref_audio"] = self._process_audio_input(ref_audio)
        if ref_text:
            payload["ref_text"] = ref_text
        if language:
            payload["language"] = language
        if model:
            payload["model"] = model
        if speaker:
            payload["speaker"] = speaker
        if instruct:
            payload["instruct"] = instruct
        if generation:
            payload["generation"] = generation

        import json
        logger.info(f"TTS 异步 API 调用: POST {self.base_url}/tts")

        client = await self._get_async_client()
        url = f"{self.base_url}/tts"
        response = await client.post(url, json=payload, timeout=self.timeout)

        logger.debug(f"TTS 异步响应状态: {response.status_code}")

        if response.status_code >= 400:
            logger.error(f"TTS 异步错误响应: {response.text[:500]}")

        response.raise_for_status()

        content_type = response.headers.get('content-type', '')
        if 'application/json' in content_type:
            data = response.json()
            audio_data = data.get('output', {}).get('audio', '')
            if audio_data.startswith('data:'):
                audio_data = audio_data.split(',', 1)[1]
            return base64.b64decode(audio_data)

        return response.content

    # ==================== VL 接口 ====================

    def vl_generate(
        self,
        prompt: str,
        image: Optional[str] = None,
        images: Optional[List[str]] = None,
        video: Optional[str] = None,
        videos: Optional[List[str]] = None,
        messages: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> str:
        """VL 视觉语言理解"""
        payload = {"prompt": prompt}

        if image:
            payload["image"] = self._process_image_input(image)
        if images:
            payload["images"] = [self._process_image_input(img) for img in images]
        if video:
            payload["video"] = video
        if videos:
            payload["videos"] = videos
        if messages:
            payload["messages"] = messages
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params
            payload["messages"] = messages
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/vl', json_data=payload)
        return response.get('output', {}).get('text', '')

    async def vl_generate_async(
        self,
        prompt: str,
        image: Optional[str] = None,
        images: Optional[List[str]] = None,
        video: Optional[str] = None,
        videos: Optional[List[str]] = None,
        messages: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> str:
        """VL 异步视觉语言理解"""
        payload = {"prompt": prompt}

        if image:
            payload["image"] = self._process_image_input(image)
        if images:
            payload["images"] = [self._process_image_input(img) for img in images]
        if video:
            payload["video"] = video
        if videos:
            payload["videos"] = videos
        if messages:
            payload["messages"] = messages
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/vl', json_data=payload)
        return response.get('output', {}).get('text', '')

    def vl_generate_stream(
        self,
        prompt: str,
        image: Optional[str] = None,
        images: Optional[List[str]] = None,
        video: Optional[str] = None,
        videos: Optional[List[str]] = None,
        messages: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Generator[str, None, None]:
        """VL 流式视觉语言理解"""
        payload = {"prompt": prompt}

        if image:
            payload["image"] = self._process_image_input(image)
        if images:
            payload["images"] = [self._process_image_input(img) for img in images]
        if video:
            payload["video"] = video
        if videos:
            payload["videos"] = videos
        if messages:
            payload["messages"] = messages
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        for chunk in self._request_stream('POST', '/vl/stream', json_data=payload):
            if 'text' in chunk:
                yield chunk['text']

    async def vl_generate_stream_async(
        self,
        prompt: str,
        image: Optional[str] = None,
        images: Optional[List[str]] = None,
        video: Optional[str] = None,
        videos: Optional[List[str]] = None,
        messages: Optional[List[Dict]] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> AsyncGenerator[str, None]:
        """VL 异步流式视觉语言理解"""
        payload = {"prompt": prompt}

        if image:
            payload["image"] = self._process_image_input(image)
        if images:
            payload["images"] = [self._process_image_input(img) for img in images]
        if video:
            payload["video"] = video
        if videos:
            payload["videos"] = videos
        if messages:
            payload["messages"] = messages
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        async for chunk in self._request_stream_async('POST', '/vl/stream', json_data=payload):
            if 'text' in chunk:
                yield chunk['text']

    # ==================== Music 接口 ====================

    def text_to_music(
        self,
        prompt: str,
        duration: float = 10.0,
        style: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """文本生成音乐"""
        payload = {
            "prompt": prompt,
            "duration": duration,
        }

        if style:
            payload["style"] = style
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/text-to-music', json_data=payload)
        return response.get('output', {})

    async def text_to_music_async(
        self,
        prompt: str,
        duration: float = 10.0,
        style: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步文本生成音乐"""
        payload = {
            "prompt": prompt,
            "duration": duration,
        }

        if style:
            payload["style"] = style
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/text-to-music', json_data=payload)
        return response.get('output', {})

    # ==================== 工具方法 ====================

    @staticmethod
    def _process_audio_input(audio: str) -> str:
        """
        处理音频输入，转换为 API 接受的格式

        Args:
            audio: base64 字符串、data URL 或文件路径

        Returns:
            API 接受的音频数据格式 (data:audio/xxx;base64,...)
        """
        if not audio:
            return audio

        # 已经是 data URL 格式，直接返回
        if audio.startswith('data:'):
            return audio

        # 检查是否是文件路径
        if Path(audio).exists():
            with open(audio, 'rb') as f:
                audio_bytes = f.read()

            # 检测音频格式
            ext = Path(audio).suffix.lower().lstrip('.')
            mime_types = {
                'wav': 'audio/wav',
                'mp3': 'audio/mpeg',
                'flac': 'audio/flac',
                'ogg': 'audio/ogg',
                'm4a': 'audio/mp4',
            }
            mime_type = mime_types.get(ext, 'audio/wav')
            base64_data = base64.b64encode(audio_bytes).decode('utf-8')
            return f"data:{mime_type};base64,{base64_data}"

        # 纯 base64 字符串，添加 data URL 前缀
        mime_type = 'audio/wav'
        return f"data:{mime_type};base64,{audio}"

    @staticmethod
    def _process_image_input(image: str) -> str:
        """
        处理图片输入，转换为 API 接受的格式

        Args:
            image: base64 字符串、data URL、HTTP URL 或文件路径

        Returns:
            API 接受的图片数据格式
        """
        # 已经是 data URL 或 HTTP URL
        if image.startswith('data:') or image.startswith('http'):
            return image

        # 可能是 base64（不含前缀）
        if not Path(image).exists():
            return image

        # 文件路径，读取并转换为 base64
        with open(image, 'rb') as f:
            image_bytes = f.read()

        # 检测媒体格式（图片 + 视频）
        ext = Path(image).suffix.lower().lstrip('.')
        mime_types = {
            'jpg': 'image/jpeg',
            'jpeg': 'image/jpeg',
            'png': 'image/png',
            'gif': 'image/gif',
            'webp': 'image/webp',
            'mp4': 'video/mp4',
            'webm': 'video/webm',
            'avi': 'video/x-msvideo',
            'mov': 'video/quicktime',
            'mkv': 'video/x-matroska',
        }
        mime_type = mime_types.get(ext, 'application/octet-stream')

        base64_data = base64.b64encode(image_bytes).decode('utf-8')
        return f"data:{mime_type};base64,{base64_data}"


# 全局客户端实例（懒加载）
_client: Optional[CoreNexusClient] = None


def get_client() -> CoreNexusClient:
    """获取全局客户端实例，优先从 config_manager 读取 base_url"""
    global _client
    if _client is None:
        from src.shared.utils.config_manager import get as cfg_get
        base_url = cfg_get("core_nexus.base_url") or config.CORE_NEXUS_BASE_URL
        _client = CoreNexusClient(base_url=base_url)
    return _client


def reset_client() -> None:
    """重置全局客户端实例（配置变更后调用）"""
    global _client
    if _client is not None:
        try:
            _client.close()
        except Exception:
            pass
        _client = None
