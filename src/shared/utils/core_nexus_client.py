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


class ApiKeyPool:
    """API Key 池管理：轮询选择、健康追踪、自动冷却"""

    def __init__(self):
        self._pools: Dict[str, List[str]] = {}   # service -> [key1, key2, ...]
        self._index: Dict[str, int] = {}          # service -> round-robin index
        self._health: Dict[str, Dict[str, float]] = {}  # service -> {key: cooldown_ts}
        self._strategy: str = "round_robin"       # round_robin | random | least_used

    def set_keys(self, service: str, keys: List[str]):
        """设置某个服务的 API Key 池"""
        if not keys:
            return
        svc = service.upper()
        self._pools[svc] = keys
        self._index.setdefault(svc, 0)
        self._health.setdefault(svc, {})
        logger.info(f"[KeyPool] {svc} 设置 {len(keys)} 个 API Key")

    def get_key(self, service: str) -> Optional[str]:
        """获取一个可用的 API Key"""
        svc = service.upper()
        pool = self._pools.get(svc, [])
        if not pool:
            return None

        now = time.time()
        available = [k for k in pool if now >= self._health.get(svc, {}).get(k, 0)]
        if not available:
            # All in cooldown — pick the one with earliest cooldown expiry
            earliest = min(pool, key=lambda k: self._health.get(svc, {}).get(k, 0))
            logger.warning(f"[KeyPool] {svc} 所有 Key 冷却中，使用最早解冻的")
            return earliest

        if self._strategy == "random":
            import random
            return random.choice(available)

        # round_robin (default)
        idx = self._index.get(svc, 0) % len(available)
        self._index[svc] = idx + 1
        return available[idx]

    def mark_cooldown(self, service: str, key: str, seconds: float = 60.0):
        """标记某个 Key 进入冷却期"""
        svc = service.upper()
        self._health.setdefault(svc, {})[key] = time.time() + seconds
        logger.warning(f"[KeyPool] {svc} Key ...{key[-6:]} 冷却 {seconds}s")

    def mark_healthy(self, service: str, key: str):
        """标记某个 Key 恢复健康"""
        svc = service.upper()
        health = self._health.get(svc, {})
        health.pop(key, None)

    def get_stats(self) -> Dict[str, Any]:
        """获取 Key 池状态"""
        now = time.time()
        stats = {}
        for svc, pool in self._pools.items():
            health = self._health.get(svc, {})
            stats[svc] = {
                "total": len(pool),
                "available": sum(1 for k in pool if now >= health.get(k, 0)),
                "cooldown": sum(1 for k in pool if now < health.get(k, 0)),
            }
        return stats


class CoreNexusClient:
    """core-nexus-ai API 客户端（支持多服务商容错 + API Key 轮换）"""

    def __init__(self, base_url: Optional[str] = None, timeout: float = 120.0):
        raw = (base_url or config.CORE_NEXUS_BASE_URL).strip()
        if raw and not raw.startswith(('http://', 'https://')):
            raw = f'http://{raw}'
        self.base_url = raw.rstrip('/')
        self.timeout = timeout

        if not self.base_url:
            raise ValueError("CORE_NEXUS_BASE_URL 未配置，请在 .env 中设置")

        self._client = httpx.Client(timeout=timeout)
        self._async_client: Optional[httpx.AsyncClient] = None

        # Failover: backup URLs for each service type
        self._fallback_urls: Dict[str, List[str]] = {}
        self._cooldown_until: Dict[str, float] = {}  # url -> cooldown timestamp

        # API Key pool
        self._key_pool = ApiKeyPool()
        self._init_key_pool()

        # 最近一次 LLM 响应的完整数据（用于 KV Cache session_id 提取等）
        self._last_response: dict = {}

        logger.info(f"CoreNexusClient 初始化 | base_url: {self.base_url}")

    def _init_key_pool(self):
        """从运行时配置初始化 API Key 池（支持逗号分隔的多 key）"""
        from src.shared.utils.config_manager import get as cfg_get

        # 优先级: config_manager(settings.json) > config.py(.env)
        api_key = cfg_get("core_nexus.api_key") or ""
        llm_key = api_key or getattr(config, "llm_key", "") or getattr(config, "LLM_KEY", "")
        key_map = {
            "LLM": llm_key,
            "TTS": getattr(config, "TTS_KEY", "") or llm_key,
            "ASR": getattr(config, "ASR_KEY", "") or llm_key,
            "VL": getattr(config, "VL_KEY", "") or llm_key,
            "MUSIC": getattr(config, "MUSIC_KEY", "") or llm_key,
            "IMAGE": llm_key,
            "VIDEO": llm_key,
        }
        for svc, raw_keys in key_map.items():
            keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
            if keys:
                self._key_pool.set_keys(svc, keys)

    def set_api_keys(self, service: str, keys: List[str]):
        """外部配置 API Key 池"""
        self._key_pool.set_keys(service, keys)

    @property
    def key_pool_stats(self) -> Dict[str, Any]:
        return self._key_pool.get_stats()

    @property
    def last_response(self) -> dict:
        """最近一次 LLM 调用的完整响应（含 session_id、cached_tokens 等元数据）"""
        return self._last_response or {}

    def set_fallback_urls(self, service: str, urls: List[str]):
        """配置备用服务商 URL

        Args:
            service: 服务类型 (LLM/TTS/ASR/VL/MUSIC)
            urls: 备用 URL 列表
        """
        self._fallback_urls[service.upper()] = [u.rstrip('/') for u in urls]

    def _get_service_from_endpoint(self, endpoint: str) -> str:
        """从端点路径推断服务类型"""
        if '/llm' in endpoint: return 'LLM'
        if '/tts' in endpoint: return 'TTS'
        if '/asr' in endpoint: return 'ASR'
        if '/vl' in endpoint: return 'VL'
        if '/music' in endpoint or '/text-to-music' in endpoint: return 'MUSIC'
        if '/text-to-image' in endpoint or '/image-to-image' in endpoint: return 'IMAGE'
        if '/text-to-video' in endpoint or '/image-to-video' in endpoint: return 'VIDEO'
        return 'UNKNOWN'

    def _is_cooled_down(self, url: str) -> bool:
        return time.time() >= self._cooldown_until.get(url, 0)

    def _cooldown(self, url: str, seconds: float = 60.0):
        self._cooldown_until[url] = time.time() + seconds
        logger.warning(f"[Failover] {url} 冷却 {seconds}s")

    def _get_active_urls(self, service: str) -> List[str]:
        """获取可用的 URL 列表（主 URL + 未冷却的备用 URL）"""
        urls = [self.base_url]
        for fb in self._fallback_urls.get(service, []):
            if fb != self.base_url and self._is_cooled_down(fb):
                urls.append(fb)
        return urls

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

    def _build_headers(self, service: str) -> Dict[str, str]:
        """构建请求头，注入 X-API-Key"""
        headers = {}
        api_key = self._key_pool.get_key(service)
        if api_key:
            headers["X-API-Key"] = api_key
        return headers, api_key

    def _request(
        self,
        method: str,
        endpoint: str,
        json_data: Optional[Dict] = None,
        max_retries: int = 3,
        **kwargs
    ) -> Dict[str, Any]:
        kwargs.setdefault('timeout', self.timeout)
        service = self._get_service_from_endpoint(endpoint)
        active_urls = self._get_active_urls(service)

        # Inject API key via X-API-Key header
        headers, api_key = self._build_headers(service)
        kwargs.setdefault('headers', {}).update(headers)

        last_error = None
        for url_base in active_urls:
            url = f"{url_base}{endpoint}"
            _masked_headers = {k: (v[:8] + '...' if len(str(v)) > 12 else v) for k, v in kwargs.get('headers', {}).items()}
            logger.info(f"[CoreNexus] {method} {url} | headers={_masked_headers}")
            if json_data:
                import json as _json
                _body_preview = _json.dumps(json_data, ensure_ascii=False)[:800]
                logger.info(f"[CoreNexus] body: {_body_preview}")

            for attempt in range(max_retries):
                try:
                    response = self._client.request(method, url, json=json_data, **kwargs)
                    response.raise_for_status()
                    if api_key:
                        self._key_pool.mark_healthy(service, api_key)
                    raw = response.text[:1000]
                    logger.info(f"[CoreNexus] {method} {url} → {response.status_code} | raw: {raw}")
                    parsed = response.json()
                    logger.info(f"[CoreNexus] parsed type={type(parsed).__name__}, keys={list(parsed.keys()) if isinstance(parsed, dict) else 'N/A'}")
                    return parsed
                except httpx.TransportError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = 0.5 * (2 ** attempt)
                        logger.warning(f"请求失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                        time.sleep(wait)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        self._cooldown(url_base, 30)
                        if api_key:
                            self._key_pool.mark_cooldown(service, api_key, 60)
                        logger.warning(f"[Failover] {url_base} 限流，切换到备用")
                        break
                    if e.response.status_code < 500:
                        logger.error(f"[CoreNexus] {method} {url} → {e.response.status_code} | {e.response.text[:500]}")
                        raise
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = 0.5 * (2 ** attempt)
                        logger.warning(f"[CoreNexus] {method} {url} → {e.response.status_code} (尝试 {attempt + 1}/{max_retries}), {wait}s 后重试 | {e.response.text[:300]}")
                        time.sleep(wait)

            if url_base != self.base_url:
                continue
            if len(active_urls) > 1:
                logger.warning(f"[Failover] {url_base} 失败，尝试备用服务")

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

        # Inject API key via X-API-Key header
        service = self._get_service_from_endpoint(endpoint)
        headers, api_key = self._build_headers(service)
        kwargs.setdefault('headers', {}).update(headers)

        _masked_headers = {k: (v[:8] + '...' if len(str(v)) > 12 else v) for k, v in kwargs.get('headers', {}).items()}
        logger.info(f"[CoreNexus] {method} {url} (stream) | headers={_masked_headers}")
        if json_data:
            import json as _json
            _body_preview = _json.dumps(json_data, ensure_ascii=False)[:800]
            logger.info(f"[CoreNexus] body: {_body_preview}")

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
        client = await self._get_async_client()
        kwargs.setdefault('timeout', self.timeout)
        service = self._get_service_from_endpoint(endpoint)
        active_urls = self._get_active_urls(service)

        # Inject API key via X-API-Key header
        headers, api_key = self._build_headers(service)
        kwargs.setdefault('headers', {}).update(headers)

        last_error = None
        for url_base in active_urls:
            url = f"{url_base}{endpoint}"
            _masked_headers = {k: (v[:8] + '...' if len(str(v)) > 12 else v) for k, v in kwargs.get('headers', {}).items()}
            logger.info(f"[CoreNexus] {method} {url} (async) | headers={_masked_headers}")
            if json_data:
                import json as _json
                _body_preview = _json.dumps(json_data, ensure_ascii=False)[:800]
                logger.info(f"[CoreNexus] body: {_body_preview}")

            for attempt in range(max_retries):
                try:
                    response = await client.request(method, url, json=json_data, **kwargs)
                    response.raise_for_status()
                    if api_key:
                        self._key_pool.mark_healthy(service, api_key)
                    return response.json()
                except httpx.TransportError as e:
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = 0.5 * (2 ** attempt)
                        logger.warning(f"异步请求失败 (尝试 {attempt + 1}/{max_retries}): {e}, {wait}s 后重试")
                        await asyncio.sleep(wait)
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        self._cooldown(url_base, 30)
                        if api_key:
                            self._key_pool.mark_cooldown(service, api_key, 60)
                        logger.warning(f"[Failover] {url_base} 限流，切换到备用")
                        break
                    if e.response.status_code < 500:
                        logger.error(f"[CoreNexus] {method} {url} → {e.response.status_code} | {e.response.text[:500]}")
                        raise
                    last_error = e
                    if attempt < max_retries - 1:
                        wait = 0.5 * (2 ** attempt)
                        logger.warning(f"[CoreNexus] {method} {url} → {e.response.status_code} (尝试 {attempt + 1}/{max_retries}), {wait}s 后重试 | {e.response.text[:300]}")
                        await asyncio.sleep(wait)

            if url_base != self.base_url:
                continue
            if len(active_urls) > 1:
                logger.warning(f"[Failover] {url_base} 失败，尝试备用服务")

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

        # Inject API key via X-API-Key header
        service = self._get_service_from_endpoint(endpoint)
        headers, api_key = self._build_headers(service)
        kwargs.setdefault('headers', {}).update(headers)

        _masked_headers = {k: (v[:8] + '...' if len(str(v)) > 12 else v) for k, v in kwargs.get('headers', {}).items()}
        logger.info(f"[CoreNexus] {method} {url} (async stream) | headers={_masked_headers}")
        if json_data:
            import json as _json
            _body_preview = _json.dumps(json_data, ensure_ascii=False)[:800]
            logger.info(f"[CoreNexus] body: {_body_preview}")

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
        provider_options: Optional[Dict] = None,
        enable_search: bool = False,
        **generation_params
    ) -> str:
        """
        LLM 文本生成

        Args:
            messages: 对话消息列表
            model: 模型名称（可选，使用默认模型）
            temperature: 温度参数
            max_tokens: 最大 token 数
            provider_options: 供应商特有参数（如 use_kv_cache, session_id）
            enable_search: 启用联网搜索（需服务端配置搜索服务）
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
        if provider_options:
            payload["provider_options"] = provider_options
        if enable_search:
            payload["enable_search"] = True

        response = self._request('POST', '/llm', json_data=payload)
        self._last_response = response
        return response.get('output', {}).get('text', '')

    async def llm_generate_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider_options: Optional[Dict] = None,
        enable_search: bool = False,
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
        if provider_options:
            payload["provider_options"] = provider_options
        if enable_search:
            payload["enable_search"] = True

        import json as _json
        print(f"[CoreNexus] POST {self.base_url}/llm | model={model} | msgs={len(messages)}{' | search=ON' if enable_search else ''}")
        print(f"[CoreNexus] body: {_json.dumps(payload, ensure_ascii=False)[:500]}")

        response = await self._request_async('POST', '/llm', json_data=payload)
        self._last_response = response
        return response.get('output', {}).get('text', '')

    def llm_generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider_options: Optional[Dict] = None,
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
        if provider_options:
            payload["provider_options"] = provider_options

        for chunk in self._request_stream('POST', '/llm/stream', json_data=payload):
            if 'text' in chunk:
                yield chunk['text']

    async def llm_generate_stream_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        provider_options: Optional[Dict] = None,
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
        if provider_options:
            payload["provider_options"] = provider_options

        import json as _json
        print(f"[CoreNexus] POST {self.base_url}/llm/stream | model={model} | msgs={len(messages)}")
        print(f"[CoreNexus] body: {_json.dumps(payload, ensure_ascii=False)[:500]}")

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
        headers, _ = self._build_headers("TTS")
        response = self._client.post(url, json=payload, timeout=self.timeout, headers=headers)

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
        headers, _ = self._build_headers("TTS")
        response = await client.post(url, json=payload, timeout=self.timeout, headers=headers)

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
        mode: Optional[str] = None,
        lyrics: Optional[str] = None,
        audio: Optional[str] = None,
        variance: Optional[float] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        extend_left: Optional[float] = None,
        extend_right: Optional[float] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """文本生成音乐（支持 generate/retake/repaint/edit/extend/cover 模式）"""
        payload = {"prompt": prompt, "duration": duration}
        for k, v in [("style", style), ("model", model), ("mode", mode),
                     ("lyrics", lyrics), ("audio", audio),
                     ("variance", variance), ("start_time", start_time),
                     ("end_time", end_time), ("extend_left", extend_left),
                     ("extend_right", extend_right)]:
            if v is not None:
                payload[k] = v
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/text-to-music', json_data=payload)
        logger.info(f"[text_to_music] mode={mode}, response type={type(response).__name__}")
        return (response or {}).get('output') or {}

    async def text_to_music_async(
        self,
        prompt: str,
        duration: float = 10.0,
        style: Optional[str] = None,
        model: Optional[str] = None,
        mode: Optional[str] = None,
        lyrics: Optional[str] = None,
        audio: Optional[str] = None,
        variance: Optional[float] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        extend_left: Optional[float] = None,
        extend_right: Optional[float] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步文本生成音乐（支持 generate/retake/repaint/edit/extend/cover 模式）"""
        payload = {"prompt": prompt, "duration": duration}
        for k, v in [("style", style), ("model", model), ("mode", mode),
                     ("lyrics", lyrics), ("audio", audio),
                     ("variance", variance), ("start_time", start_time),
                     ("end_time", end_time), ("extend_left", extend_left),
                     ("extend_right", extend_right)]:
            if v is not None:
                payload[k] = v
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/text-to-music', json_data=payload)
        return (response or {}).get('output') or {}

    def music_to_music(
        self,
        audio: str,
        prompt: Optional[str] = None,
        style: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """音乐风格迁移（/music-to-music 端点）"""
        payload = {"audio": audio}
        if prompt:
            payload["prompt"] = prompt
        if style:
            payload["style"] = style
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/music-to-music', json_data=payload)
        logger.info(f"[music_to_music] response type={type(response).__name__}")
        return (response or {}).get('output') or {}

    async def music_to_music_async(
        self,
        audio: str,
        prompt: Optional[str] = None,
        style: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步音乐风格迁移（/music-to-music 端点）"""
        payload = {"audio": audio}
        if prompt:
            payload["prompt"] = prompt
        if style:
            payload["style"] = style
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/music-to-music', json_data=payload)
        return (response or {}).get('output') or {}

    # ==================== Image Generation 接口 ====================

    def text_to_image(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        model: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        ref_image: Optional[str] = None,
        ref_strength: float = 0.4,
        **generation_params
    ) -> Dict[str, Any]:
        """文本生成图片（POST /text-to-image）"""
        payload = {"prompt": prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if model:
            payload["model"] = model
        generation = {"width": width, "height": height}
        generation.update(generation_params)
        payload["generation"] = generation

        response = self._request('POST', '/text-to-image', json_data=payload)
        return self._extract_image_output(response)

    async def text_to_image_async(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        model: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        ref_image: Optional[str] = None,
        ref_strength: float = 0.4,
        **generation_params
    ) -> Dict[str, Any]:
        """异步文本生成图片（POST /text-to-image）"""
        payload = {"prompt": prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if model:
            payload["model"] = model
        generation = {"width": width, "height": height}
        generation.update(generation_params)
        payload["generation"] = generation

        response = await self._request_async('POST', '/text-to-image', json_data=payload)
        return self._extract_image_output(response)

    def image_to_image(
        self,
        prompt: str,
        image: str,
        mask: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """图像编辑（POST /image-to-image）"""
        payload = {
            "prompt": prompt,
            "image": self._process_image_input(image),
        }
        if mask:
            payload["mask"] = self._process_image_input(mask)
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/image-to-image', json_data=payload)
        return self._extract_image_output(response)

    async def image_to_image_async(
        self,
        prompt: str,
        image: str,
        mask: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步图像编辑（POST /image-to-image）"""
        payload = {
            "prompt": prompt,
            "image": self._process_image_input(image),
        }
        if mask:
            payload["mask"] = self._process_image_input(mask)
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/image-to-image', json_data=payload)
        return self._extract_image_output(response)

    @staticmethod
    def _extract_image_output(response: Dict) -> Dict[str, Any]:
        """从 core-nexus-ai 响应中提取图片数据"""
        output = (response or {}).get('output') or {}
        image_data = output.get('image', '')
        if not image_data:
            return {"image": None}
        result = {"image": image_data}
        if image_data.startswith('data:'):
            header, b64 = image_data.split(',', 1)
            result["image_bytes"] = base64.b64decode(b64)
            result["image_base64"] = b64
        elif image_data.startswith('http://') or image_data.startswith('https://'):
            # core-nexus 返回图片 URL，下载获取字节
            import requests
            resp = requests.get(image_data, timeout=60)
            resp.raise_for_status()
            result["image_bytes"] = resp.content
            result["image_base64"] = base64.b64encode(resp.content).decode('utf-8')
        else:
            result["image_bytes"] = base64.b64decode(image_data)
            result["image_base64"] = image_data
        return result

    # ==================== Video Generation 接口 ====================

    def text_to_video(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """文本生成视频（POST /text-to-video）"""
        payload = {"prompt": prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/text-to-video', json_data=payload, timeout=600)
        return self._extract_video_output(response)

    async def text_to_video_async(
        self,
        prompt: str,
        negative_prompt: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步文本生成视频（POST /text-to-video）"""
        payload = {"prompt": prompt}
        if negative_prompt:
            payload["negative_prompt"] = negative_prompt
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/text-to-video', json_data=payload, timeout=600)
        return self._extract_video_output(response)

    def image_to_video(
        self,
        image: str,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """图像生成视频（POST /image-to-video）"""
        payload = {"image": self._process_image_input(image)}
        if prompt:
            payload["prompt"] = prompt
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = self._request('POST', '/image-to-video', json_data=payload, timeout=600)
        return self._extract_video_output(response)

    async def image_to_video_async(
        self,
        image: str,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
        **generation_params
    ) -> Dict[str, Any]:
        """异步图像生成视频（POST /image-to-video）"""
        payload = {"image": self._process_image_input(image)}
        if prompt:
            payload["prompt"] = prompt
        if model:
            payload["model"] = model
        if generation_params:
            payload["generation"] = generation_params

        response = await self._request_async('POST', '/image-to-video', json_data=payload, timeout=600)
        return self._extract_video_output(response)

    @staticmethod
    def _extract_video_output(response: Dict) -> Dict[str, Any]:
        """从 core-nexus-ai 响应中提取视频数据"""
        output = (response or {}).get('output') or {}
        video_data = output.get('video', '')
        if not video_data:
            return {"video": None}
        result = {"video": video_data}
        if video_data.startswith('data:'):
            header, b64 = video_data.split(',', 1)
            result["video_bytes"] = base64.b64decode(b64)
            result["video_base64"] = b64
        else:
            result["video_bytes"] = base64.b64decode(video_data)
            result["video_base64"] = video_data
        return result

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
            file_size = Path(audio).stat().st_size
            max_size = 100 * 1024 * 1024  # 100MB 限制，防止 OOM
            if file_size > max_size:
                raise ValueError(f"音频文件过大 ({file_size / 1024 / 1024:.1f}MB)，超过 100MB 限制，请先压缩或截取")

            # 对大于 20MB 的文件分块读取编码，降低峰值内存
            if file_size > 20 * 1024 * 1024:
                import io
                chunks = []
                with open(audio, 'rb') as f:
                    while True:
                        chunk = f.read(8 * 1024 * 1024)  # 8MB chunks
                        if not chunk:
                            break
                        chunks.append(base64.b64encode(chunk).decode('utf-8'))
                base64_data = ''.join(chunks)
            else:
                with open(audio, 'rb') as f:
                    audio_bytes = f.read()
                base64_data = base64.b64encode(audio_bytes).decode('utf-8')

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
        file_size = Path(image).stat().st_size
        max_size = 50 * 1024 * 1024  # 50MB 限制
        if file_size > max_size:
            raise ValueError(f"媒体文件过大 ({file_size / 1024 / 1024:.1f}MB)，超过 50MB 限制")

        if file_size > 20 * 1024 * 1024:
            import io
            chunks = []
            with open(image, 'rb') as f:
                while True:
                    chunk = f.read(8 * 1024 * 1024)
                    if not chunk:
                        break
                    chunks.append(base64.b64encode(chunk).decode('utf-8'))
            base64_data = ''.join(chunks)
        else:
            with open(image, 'rb') as f:
                image_bytes = f.read()
            base64_data = base64.b64encode(image_bytes).decode('utf-8')

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
