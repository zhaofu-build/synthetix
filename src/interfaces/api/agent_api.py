"""
对话式剪辑 Agent API

提供对话式视频剪辑的 REST API 接口
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio

from src.agent import VideoDialogAgent, get_video_agent
from src.shared.models.response import success_response, error_response

router = APIRouter()


# ==================== 请求/响应模型 ====================

class ChatRequest(BaseModel):
    """对话请求"""
    session_id: Optional[str] = None
    project_id: Optional[int] = None
    message: str
    context: Optional[Dict[str, Any]] = None


class ChatResponse(BaseModel):
    """对话响应"""
    session_id: str
    reply: str
    status: str  # idle, collecting. confirming. executing. completed. error
    action: Optional[Dict[str, Any]] = None
    result: Optional[Dict[str, Any]] = None
    suggestions: Optional[List[str]] = None
    missing_slots: Optional[List[str]] = None


class ExecuteRequest(BaseModel):
    """直接执行请求"""
    tool: str
    params: Dict[str, Any]


# ==================== 对话接口 ====================

@router.post("/chat", summary="处理对话消息")
async def chat(request: ChatRequest) -> Dict[str, Any]:
    """
    处理对话消息

    支持多轮对话，自动管理会话状态

    Args:
        request: 对话请求

    Returns:
        对话响应
    """
    try:
        agent = get_video_agent()
        result = await agent.process_message(
            session_id=request.session_id,
            user_input=request.message,
            context=request.context
        )

        return success_response(data=result)

    except Exception as e:
        return error_response(
            error="ChatError",
            message=str(e),
            code=500
        )


@router.post("/chat/stream", summary="流式对话")
async def chat_stream(request: ChatRequest):
    """
    流式对话（SSE）

    返回 Server-Sent Events 流式响应

    Args:
        request: 对话请求

    Returns:
        SSE 流
    """
    async def generate():
        try:
            agent = get_video_agent()

            # 先发送处理中状态
            yield f"data: {json.dumps({'status': 'processing'}, ensure_ascii=False)}\n\n"

            # 处理消息
            result = await agent.process_message(
                session_id=request.session_id,
                user_input=request.message,
                context=request.context
            )

            # 流式发送响应
            yield f"data: {json.dumps(result, ensure_ascii=False)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"

        yield "data: [DONE]\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ==================== 直接执行接口 ====================

@router.post("/execute", summary="直接执行工具")
async def execute_tool(request: ExecuteRequest) -> Dict[str, Any]:
    """
    直接执行工具（跳过对话）

    Args:
        request: 执行请求

    Returns:
        执行结果
    """
    from src.agent.tool_registry import registry

    tool = registry.get_tool(request.tool)
    if not tool:
        return error_response(
            error="ToolNotFound",
            message=f"工具 '{request.tool}' 不存在",
            code=404
        )

    try:
        result = await tool.execute(**request.params)
        return success_response(data=result)

    except Exception as e:
        return error_response(
            error="ExecutionError",
            message=str(e),
            code=500
        )


# ==================== 视频分析接口 ====================

@router.post("/analyze/{video_id}", summary="分析视频")
async def analyze_video(video_id: int) -> Dict[str, Any]:
    """
    分析视频内容

    Args:
        video_id: 视频 ID

    Returns:
        分析结果
    """
    from src.agent.tool_registry import registry

    tool = registry.get_tool("analyze_video")
    if not tool:
        return error_response(
            error="ToolNotFound",
            message="分析工具不可用",
            code=500
        )

    try:
        result = await tool.execute(video_id=video_id)
        return success_response(data=result)

    except Exception as e:
        return error_response(
            error="AnalysisError",
            message=str(e),
            code=500
        )


# ==================== 工具列表接口 ====================

@router.get("/tools", summary="获取可用工具列表")
async def list_tools() -> Dict[str, Any]:
    """
    获取所有可用工具

    Returns:
        工具列表
    """
    from src.agent.tool_registry import registry

    tools = []
    for tool in registry.list_tools():
        tools.append({
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters,
            "examples": tool.examples
        })

    return success_response(data={
        "tools": tools,
        "count": len(tools)
    })


# ==================== 会话管理接口 ====================

@router.delete("/session/{session_id}", summary="删除会话")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """
    删除会话

    Args:
        session_id: 会话 ID

    Returns:
        删除结果
    """
    from src.agent.session_manager import get_session_manager

    manager = get_session_manager()
    success = manager.delete_session(session_id)

    if success:
        return success_response(message="会话已删除")
    else:
        return error_response(
            error="SessionNotFound",
            message="会话不存在",
            code=404
        )


@router.get("/sessions", summary="获取活跃会话列表")
async def list_sessions() -> Dict[str, Any]:
    """
    获取所有活跃会话

    Returns:
        会话列表
    """
    from src.agent.session_manager import get_session_manager

    manager = get_session_manager()
    sessions = manager.get_active_sessions()

    return success_response(data={
        "sessions": [
            {
                "session_id": s.session_id,
                "status": s.status.value,
                "intent": s.intent,
                "created_at": s.created_at,
                "updated_at": s.updated_at
            }
            for s in sessions
        ],
        "count": len(sessions)
    })
