"""
WebSocket 端点

提供实时双向通信通道：
- /ws — 主通道：Agent 对话流式响应、工具执行状态
- /ws/render — 渲染进度推送
- /ws/system — 系统通知
"""
import json
import logging
import asyncio
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)
router = APIRouter()


class ConnectionManager:
    """WebSocket 连接管理器"""

    def __init__(self):
        self.active: Dict[str, Set[WebSocket]] = {
            "main": set(),
            "render": set(),
            "system": set(),
        }

    async def connect(self, ws: WebSocket, channel: str = "main"):
        await ws.accept()
        if channel not in self.active:
            self.active[channel] = set()
        self.active[channel].add(ws)
        logger.info(f"WebSocket 连接: channel={channel}, 当前连接数={len(self.active[channel])}")

    def disconnect(self, ws: WebSocket, channel: str = "main"):
        self.active.get(channel, set()).discard(ws)

    async def broadcast(self, channel: str, data: dict):
        """向频道内所有连接广播消息"""
        connections = self.active.get(channel, set())
        dead = []
        for ws in connections:
            try:
                await ws.send_json(data)
            except Exception:
                dead.append(ws)
        for ws in dead:
            connections.discard(ws)

    async def send_to(self, ws: WebSocket, data: dict):
        """发送消息到单个连接"""
        try:
            await ws.send_json(data)
        except Exception:
            pass


manager = ConnectionManager()


async def _main_handler(ws: WebSocket):
    """主 WS 通道处理"""
    await manager.connect(ws, "main")
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send_json({"type": "error", "message": "无效的 JSON"})
                continue

            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await ws.send_json({"type": "pong"})
            elif msg_type == "chat":
                # 通过 WS 进行 Agent 对话
                from src.agent.react_agent import get_react_agent
                agent = get_react_agent()
                try:
                    async for event in agent.process_message_stream(
                        session_id=msg.get("session_id"),
                        user_input=msg.get("message", ""),
                        context=msg.get("context"),
                    ):
                        await ws.send_json(event)
                    await ws.send_json({"type": "ws_done"})
                except Exception as e:
                    await ws.send_json({"type": "error", "message": str(e)})
            else:
                await ws.send_json({"type": "unknown", "message": f"未知消息类型: {msg_type}"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, "main")


async def _render_handler(ws: WebSocket):
    """渲染进度 WS 通道"""
    await manager.connect(ws, "render")
    try:
        while True:
            raw = await ws.receive_text()
            # 渲染通道主要推送，接收仅用于心跳
            if raw.strip() == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, "render")


async def _system_handler(ws: WebSocket):
    """系统通知 WS 通道"""
    await manager.connect(ws, "system")
    try:
        while True:
            raw = await ws.receive_text()
            if raw.strip() == "ping":
                await ws.send_json({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(ws, "system")


@router.websocket("/ws")
async def ws_main(ws: WebSocket):
    await _main_handler(ws)


@router.websocket("/ws/render")
async def ws_render(ws: WebSocket):
    await _render_handler(ws)


@router.websocket("/ws/system")
async def ws_system(ws: WebSocket):
    await _system_handler(ws)
