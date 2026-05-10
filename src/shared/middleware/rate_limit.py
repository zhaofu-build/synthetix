"""
轻量级速率限制中间件

基于 IP + 路径前缀的滑动窗口计数器，无外部依赖。
"""
import time
import logging
from collections import defaultdict
from typing import Dict, Tuple

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """基于内存的速率限制中间件"""

    def __init__(self, app, default_limit: int = 60, default_window: int = 60):
        """
        Args:
            default_limit: 默认窗口内最大请求数
            default_window: 默认窗口大小（秒）
        """
        super().__init__(app)
        self.default_limit = default_limit
        self.default_window = default_window
        # {prefix: (limit, window_seconds)}
        self._rules: Dict[str, Tuple[int, int]] = {
            "/api/agent": (20, 60),        # AI 对话：20次/分钟
            "/api/core-nexus": (10, 60),    # AI 服务代理：10次/分钟
            "/api/audios/tts": (10, 60),    # TTS：10次/分钟
        }
        # {key: [timestamps]}
        self._counters: Dict[str, list] = defaultdict(list)
        self._cleanup_interval = 300  # 每 5 分钟清理过期计数器
        self._last_cleanup = time.time()

    def _get_rule(self, path: str) -> Tuple[int, int]:
        for prefix, rule in self._rules.items():
            if path.startswith(prefix):
                return rule
        return self.default_limit, self.default_window

    def _cleanup(self):
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        self._last_cleanup = now
        expired = [k for k, ts in self._counters.items() if not ts or now - ts[-1] > self.default_window]
        for k in expired:
            del self._counters[k]

    def _check(self, key: str, limit: int, window: int) -> bool:
        now = time.time()
        timestamps = self._counters[key]
        # 移除窗口外的记录
        cutoff = now - window
        while timestamps and timestamps[0] < cutoff:
            timestamps.pop(0)
        if len(timestamps) >= limit:
            return False
        timestamps.append(now)
        return True

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        # 只限制 API 路由
        if not path.startswith("/api/"):
            return await call_next(request)

        limit, window = self._get_rule(path)
        client_ip = request.client.host if request.client else "unknown"
        key = f"{client_ip}:{path}"

        self._cleanup()

        if not self._check(key, limit, window):
            logger.warning("速率限制触发: %s (limit=%d/%ds)", key, limit, window)
            return JSONResponse(
                status_code=429,
                content={"error": "RateLimitError", "message": "请求过于频繁，请稍后重试"},
            )

        return await call_next(request)
