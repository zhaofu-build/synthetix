"""
core-nexus-ai API 客户端

统一的 HTTP 客户端，用于调用 core-nexus-ai 服务
"""
import base64
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List, Generator
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
        self.base_url = (base_url or config.CORE_NEXUS_BASE_URL).rstrip('/')
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("CORE_NEXUS_BASE_URL 未配置，请在 .env 中设置")

        logger.info(f"CoreNexusClient 初始化 | base_url: {self.base_url}")

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        发送 HTTP 请求

        Args:
            method: HTTP 方法
            endpoint: API 端点
            json_data: JSON 请求数据
            **kwargs: 其他请求参数

        Returns:
            响应 JSON 数据

        Raises:
            httpx.HTTPError: HTTP 请求错误
        """
        url = f"{self.base_url}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)

        logger.debug(f"API 请求: {method} {url}")

        with httpx.Client() as client:
            response = client.request(method, url, json=json_data, **kwargs)
            response.raise_for_status()
            return response.json()

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

        with httpx.Client() as client:
            with client.stream(method, url, json=json_data, **kwargs) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if line.startswith('data: '):
                        data = line[6:]  # 去掉 'data: ' 前缀
                        if data == '[DONE]':
                            break
                        import json
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

        Args:
            messages: 对话消息列表
            model: 模型名称（可选）
            temperature: 温度参数
            max_tokens: 最大 token 数
            **generation_params: 其他生成参数

        Yields:
            生成的文本片段
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

    # ==================== ASR 接口 ====================

    def asr_transcribe(
        self,
        audio: str,
        language: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """
        ASR 语音识别

        Args:
            audio: 音频数据（base64、data URL 或文件路径）
            language: 语言代码（可选）
            **generation_params: 其他生成参数

        Returns:
            包含 text, language, segments 的字典
        """
        # 处理音频输入
        audio_data = self._process_audio_input(audio)

        payload = {
            "audio": audio_data,
        }
        if language:
            payload["language"] = language
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/asr', json_data=payload)
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
        """
        TTS 文本转语音

        Args:
            text: 要合成的文本
            model: 模型名称（可选）
            speaker: 说话人（可选）
            ref_audio: 参考音频（可选，用于语音克隆）
            ref_text: 参考音频文本（可选）
            language: 语言（默认 Auto）
            instruct: 指令文本（可选）
            generation: 生成参数字典

        Returns:
            音频二进制数据
        """
        payload = {"text": text}

        # 只添加非空参数
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

        # 打印完整请求参数（调试用）
        import json
        logger.info(f"TTS API 调用: POST {self.base_url}/tts")
        logger.info(f"TTS 完整请求参数: {json.dumps(payload, ensure_ascii=False, indent=2)}")

        url = f"{self.base_url}/tts"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)

            logger.debug(f"TTS 响应状态: {response.status_code}")

            if response.status_code >= 400:
                logger.error(f"TTS 错误响应: {response.text[:500]}")

            response.raise_for_status()

            # 如果返回 JSON（包含 base64 音频）
            content_type = response.headers.get('content-type', '')
            if 'application/json' in content_type:
                data = response.json()
                audio_data = data.get('output', {}).get('audio', '')
                if audio_data.startswith('data:'):
                    audio_data = audio_data.split(',', 1)[1]
                return base64.b64decode(audio_data)

            # 直接返回音频二进制
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
        **generation_params
    ) -> str:
        """
        VL 视觉语言理解

        Args:
            prompt: 提示词
            image: 单张图片（本地路径、base64、data URL 或 HTTP URL）
            images: 多张图片列表
            video: 单个视频（本地路径、HTTP URL、base64 或 data URL）
            videos: 多个视频列表
            messages: 多轮对话消息（包含图片/视频）
            **generation_params: 其他生成参数

        Returns:
            生成的文本
        """
        payload = {
            "prompt": prompt,
        }

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
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/vl', json_data=payload)
        return response.get('output', {}).get('text', '')

    def vl_generate_stream(
        self,
        prompt: str,
        image: Optional[str] = None,
        images: Optional[List[str]] = None,
        video: Optional[str] = None,
        videos: Optional[List[str]] = None,
        messages: Optional[List[Dict]] = None,
        **generation_params
    ) -> Generator[str, None, None]:
        """
        VL 流式视觉语言理解

        Args:
            prompt: 提示词
            image: 单张图片
            images: 多张图片列表
            video: 单个视频
            videos: 多个视频列表
            messages: 多轮对话消息
            **generation_params: 其他生成参数

        Yields:
            生成的文本片段
        """
        payload = {
            "prompt": prompt,
        }

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
        if generation_params:
            payload["generation"] = generation_params

        for chunk in self._request_stream('POST', '/vl/stream', json_data=payload):
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
        """
        文本生成音乐

        Args:
            prompt: 音乐描述，如 "轻快的电子音乐"
            duration: 音乐时长（秒），默认 10 秒
            style: 风格：pop, classical, electronic, jazz, rock, ambient, hiphop
            model: 模型名称（可选）
            **generation_params: 其他生成参数

        Returns:
            包含 audio, format, duration, sample_rate 的字典
        """
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
        # 尝试从 base64 内容检测格式（默认使用 wav）
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
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = CoreNexusClient()
    return _client
