"""
CDP (Chrome DevTools Protocol) 浏览器自动化

通过 CDP 协议控制 Chrome/Chromium 浏览器，
支持网页截图、内容提取、文件下载等操作。
"""
import json
import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class CDPBrowser:
    """通过 WebSocket 连接 Chrome DevTools Protocol"""

    def __init__(self):
        self._ws = None
        self._msg_id = 0
        self._pending: Dict[int, asyncio.Future] = {}
        self._reader_task: Optional[asyncio.Task] = None
        self._cdp_url: Optional[str] = None

    def _get_cdp_url(self) -> str:
        """获取 CDP WebSocket URL"""
        import os
        url = os.getenv("CHROME_CDP_URL", "")
        if url:
            return url
        # 默认尝试连接本地 Chrome 调试端口
        return "http://127.0.0.1:9222"

    async def _ensure_connected(self):
        """确保 CDP 连接"""
        if self._ws and not self._ws.closed:
            return

        import httpx
        cdp_url = self._get_cdp_url()
        self._cdp_url = cdp_url

        # 获取 WebSocket 调试 URL
        async with httpx.AsyncClient(timeout=5.0) as client:
            try:
                resp = await client.get(f"{cdp_url}/json/version")
                data = resp.json()
                ws_url = data.get("webSocketDebuggerUrl")
            except Exception:
                # 尝试获取第一个 tab
                resp = await client.get(f"{cdp_url}/json")
                tabs = resp.json()
                if not tabs:
                    raise RuntimeError("未找到 Chrome 调试标签页")
                ws_url = tabs[0].get("webSocketDebuggerUrl")

        if not ws_url:
            raise RuntimeError("无法获取 Chrome CDP WebSocket URL")

        import websockets
        self._ws = await websockets.connect(ws_url, max_size=10 * 1024 * 1024)
        self._reader_task = asyncio.create_task(self._read_loop())
        logger.info(f"CDP 已连接: {ws_url}")

    async def _read_loop(self):
        """读取 CDP 响应"""
        try:
            async for msg in self._ws:
                data = json.loads(msg)
                msg_id = data.get("id")
                if msg_id and msg_id in self._pending:
                    fut = self._pending.pop(msg_id)
                    if not fut.done():
                        fut.set_result(data)
        except Exception as e:
            logger.debug(f"CDP 读循环结束: {e}")
            # 清理 pending
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(ConnectionError("CDP 连接断开"))
            self._pending.clear()

    async def _send(self, method: str, params: Dict = None) -> Dict:
        """发送 CDP 命令并等待响应"""
        await self._ensure_connected()
        self._msg_id += 1
        msg = {"id": self._msg_id, "method": method, "params": params or {}}
        fut = asyncio.get_event_loop().create_future()
        self._pending[self._msg_id] = fut
        await self._ws.send(json.dumps(msg))

        try:
            result = await asyncio.wait_for(fut, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending.pop(self._msg_id, None)
            raise RuntimeError(f"CDP 命令超时: {method}")

        if "error" in result:
            raise RuntimeError(f"CDP 错误: {result['error'].get('message', '')}")
        return result.get("result", {})

    async def navigate(self, url: str, wait_ms: int = 2000) -> Dict[str, Any]:
        """导航到 URL"""
        result = await self._send("Page.navigate", {"url": url})
        await asyncio.sleep(wait_ms / 1000)
        return {"success": True, "url": url, "frame_id": result.get("frameId", "")}

    async def screenshot(self, save_path: str = None, full_page: bool = False) -> Dict[str, Any]:
        """截取页面截图"""
        params = {"format": "png"}
        if full_page:
            params["captureBeyondViewport"] = True

        result = await self._send("Page.captureScreenshot", params)
        data_b64 = result.get("data", "")

        if save_path and data_b64:
            import base64
            path = Path(save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(base64.b64decode(data_b64))
            return {"success": True, "path": str(path), "size": len(base64.b64decode(data_b64))}

        return {"success": True, "data_length": len(data_b64)}

    async def get_content(self) -> Dict[str, Any]:
        """获取页面 DOM 内容"""
        result = await self._send("Runtime.evaluate", {
            "expression": "document.body.innerText",
            "returnByValue": True,
        })
        text = result.get("result", {}).get("value", "")
        return {"success": True, "content": text[:5000]}

    async def get_page_links(self) -> Dict[str, Any]:
        """提取页面所有链接"""
        js = """
        Array.from(document.querySelectorAll('a[href]')).map(a => ({
            text: a.innerText.trim().slice(0, 100),
            href: a.href
        })).filter(l => l.text && l.href.startsWith('http'))
        """
        result = await self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        links = result.get("result", {}).get("value", [])
        return {"success": True, "links": links[:50], "count": len(links)}

    async def click_element(self, selector: str) -> Dict[str, Any]:
        """点击页面元素"""
        js = f"""
        (function() {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return {{success: false, error: '元素未找到'}};
            el.click();
            return {{success: true}};
        }})()
        """
        result = await self._send("Runtime.evaluate", {
            "expression": js,
            "returnByValue": True,
        })
        return result.get("result", {}).get("value", {"success": False})

    async def execute_js(self, expression: str) -> Dict[str, Any]:
        """执行 JavaScript"""
        result = await self._send("Runtime.evaluate", {
            "expression": expression,
            "returnByValue": True,
        })
        value = result.get("result", {}).get("value")
        return {"success": True, "result": value}

    async def close(self):
        """关闭连接"""
        if self._reader_task:
            self._reader_task.cancel()
        if self._ws and not self._ws.closed:
            await self._ws.close()
        self._ws = None


# 全局单例
_browser: Optional[CDPBrowser] = None


def get_cdp_browser() -> CDPBrowser:
    global _browser
    if _browser is None:
        _browser = CDPBrowser()
    return _browser
