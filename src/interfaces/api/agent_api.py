"""
对话式剪辑 Agent API

提供对话式视频剪辑的 REST API 接口
"""
from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import json
import asyncio

from src.agent.react_agent import get_react_agent
from src.shared.models.response import success_response, error_response
from src.shared.exceptions.exceptions import ValidationException, ResourceNotFoundException, ExternalServiceException

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


class DeepResearchRequest(BaseModel):
    """深度研究请求"""
    session_id: Optional[str] = None
    project_id: Optional[int] = None
    message: str
    context: Optional[Dict[str, Any]] = None


# ==================== 对话接口 ====================

@router.post("/chat", summary="处理对话消息")
async def chat(request: ChatRequest):
    """
    处理对话消息

    支持多轮对话，自动管理会话状态

    Args:
        request: 对话请求

    Returns:
        对话响应
    """
    agent = get_react_agent()
    result = await agent.process_message(
        session_id=request.session_id,
        user_input=request.message,
        context=request.context
    )

    return success_response(data=result)


@router.post("/chat/stream", summary="流式对话")
async def chat_stream(request: ChatRequest):
    """
    流式对话（SSE）— 逐步推送 AI 思考、工具执行和回复

    事件类型: session, thinking, tool_start, tool_result, reply, done, error

    Args:
        request: 对话请求

    Returns:
        SSE 流
    """
    async def event_generator():
        try:
            agent = get_react_agent()
            async for event in agent.process_message_stream(
                session_id=request.session_id,
                user_input=request.message,
                context=request.context
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("SSE 流式处理失败: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': '处理请求时发生错误，请稍后重试'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# ==================== 深度研究接口 ====================

@router.post("/deep-research", summary="深度研究模式")
async def deep_research(request: DeepResearchRequest):
    """
    深度研究模式（SSE）— 多阶段分析→规划→执行

    适用于复杂剪辑需求，自动分阶段处理。
    """
    async def event_generator():
        try:
            agent = get_react_agent()
            async for event in agent.process_deep_research(
                session_id=request.session_id,
                user_input=request.message,
                context=request.context,
            ):
                yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            logger.error("SSE 流式处理失败: %s", e)
            yield f"data: {json.dumps({'type': 'error', 'message': '处理请求时发生错误，请稍后重试'}, ensure_ascii=False)}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


# ==================== 方案模式接口 ====================

PLAN_SYSTEM_PROMPT = """你是视频剪辑方案规划器。用户会描述剪辑需求，你需要生成一个结构化的操作列表。

严格要求：输出 JSON 格式的操作列表，不要包含其他文字。

格式：
{
  "summary": "方案概述（一句话）",
  "operations": [
    {
      "type": "操作类型（cut/merge/add_subtitle/add_audio/change_speed/generate_tts）",
      "tool": "对应的工具名（cut_video/merge_videos/add_subtitle/add_audio/change_speed/generate_tts）",
      "params": {"参数名": "参数值"},
      "description": "人类可读的操作描述",
      "risk": "safe 或 needs_confirm 或 destructive"
    }
  ]
}

风险等级说明：
- safe: 只读操作、无损操作（如分析、查看、生成TTS）
- needs_confirm: 修改视频的操作（如剪切、添加字幕、调整速度）
- destructive: 删除素材、覆盖文件等不可逆操作

注意事项：
- cut_video 参数需要 video_id, start_time, end_time
- merge_videos 参数需要 video_ids 列表
- 时间格式为 HH:MM:SS
"""


@router.post("/plan", summary="生成剪辑方案")
async def generate_plan(request: ChatRequest):
    """
    生成结构化剪辑方案（方案模式）

    返回一组可编辑、可逐一确认的操作卡片。
    """
    from src.shared.utils.core_nexus_client import get_client
    from src.shared.utils.config_manager import get as cfg_get

    client = get_client()
    model = cfg_get("core_nexus.model") or None

    # 获取可用工具描述
    agent = get_react_agent()
    from src.agent.tool_registry import registry
    tools_desc = "\n".join(
        f"- {t.name}: {t.description}"
        for t in registry.list_tools()
        if t.name in ["cut_video", "merge_videos", "add_subtitle", "add_audio",
                      "change_speed", "generate_tts", "smart_clip",
                      "transcribe_video", "analyze_transcript", "extract_audio"]
    )

    messages = [
        {"role": "system", "content": PLAN_SYSTEM_PROMPT + f"\n\n可用工具：\n{tools_desc}"},
        {"role": "user", "content": request.message}
    ]

    response = client.llm_generate(messages=messages, model=model)
    plan_text = response.get("text", "")

    # 尝试解析 JSON
    import re
    json_match = re.search(r'\{[\s\S]*\}', plan_text)
    if json_match:
        try:
            plan_data = json.loads(json_match.group())
        except json.JSONDecodeError:
            plan_data = {
                "summary": "方案生成完成（格式解析失败）",
                "operations": [],
                "raw": plan_text
            }
    else:
        plan_data = {
            "summary": plan_text[:200],
            "operations": [],
            "raw": plan_text
        }

    return success_response(data=plan_data)


# ==================== 直接执行接口 ====================

@router.post("/execute", summary="直接执行工具")
async def execute_tool(request: ExecuteRequest):
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
        raise ResourceNotFoundException(resource_type="Tool", resource_id=request.tool)

    result = await tool.execute(**request.params)
    return success_response(data=result)


# ==================== 视频分析接口 ====================

@router.post("/analyze/{video_id}", summary="分析视频")
async def analyze_video(video_id: int):
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
        raise ResourceNotFoundException(resource_type="Tool", resource_id="analyze_video")

    result = await tool.execute(video_id=video_id)
    return success_response(data=result)


# ==================== 工具列表接口 ====================

@router.get("/tools", summary="获取可用工具列表")
async def list_tools():
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
async def delete_session(session_id: str):
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

    # 清理会话关联的临时文件
    if success:
        try:
            from src.infrastructure.db.session import get_db_context
            from src.infrastructure.repositories.temp_file_repository import TempFileRepository
            with get_db_context() as db:
                temp_repo = TempFileRepository(db)
                temp_repo.delete_by_session(session_id)
                db.commit()
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f"清理会话临时文件失败: {e}")

    if success:
        return success_response(message="会话已删除")
    else:
        return error_response(
            error="SessionNotFound",
            message="会话不存在",
            code=404
        )


@router.delete("/sessions/project/{project_id}", summary="删除项目所有会话")
async def delete_project_sessions(project_id: int):
    """删除指定项目的所有会话（清除聊天记录时调用）"""
    from src.agent.session_manager import get_session_manager
    manager = get_session_manager()
    count = manager.delete_sessions_by_project(project_id)
    return success_response(message=f"已删除 {count} 个会话")


@router.get("/sessions", summary="获取活跃会话列表")
async def list_sessions():
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


@router.get("/sessions/by-project/{project_id}", summary="获取项目会话")
async def list_sessions_by_project(project_id: int):
    """获取指定项目的所有会话"""
    from src.agent.session_manager import get_session_manager
    manager = get_session_manager()
    sessions = manager.get_sessions_by_project(project_id)
    return success_response(data={
        "sessions": [
            {
                "session_id": s.session_id,
                "status": s.status.value,
                "intent": s.intent,
                "history_count": len(s.history),
                "created_at": s.created_at,
                "updated_at": s.updated_at,
            }
            for s in sessions
        ],
        "count": len(sessions),
    })


@router.post("/sessions/restore/{project_id}", summary="恢复项目最近会话")
async def restore_session(project_id: int):
    """恢复项目最近一次会话"""
    from src.agent.session_manager import get_session_manager
    manager = get_session_manager()
    session = manager.restore_last_session(project_id)
    if not session:
        return success_response(data=None, message="该项目暂无历史会话")
    return success_response(data={
        "session_id": session.session_id,
        "status": session.status.value,
        "history_count": len(session.history),
        "last_user_message": session.get_last_user_message(),
        "updated_at": session.updated_at,
    })


# ==================== 批量执行 ====================

class BatchExecuteRequest(BaseModel):
    tasks: List[Dict[str, Any]] = []
    """[{tool, params}]"""


@router.post("/batch/execute", summary="批量执行工具")
async def batch_execute(request: BatchExecuteRequest):
    """批量执行多个工具任务"""
    from src.agent.tool_registry import registry as tool_registry
    from src.agent.session_manager import get_session_manager
    import asyncio

    if not request.tasks:
        return error_response(message="任务列表为空")

    results = []
    for task in request.tasks[:20]:  # max 20 tasks per batch
        tool_name = task.get("tool")
        params = task.get("params", {})
        tool = tool_registry.get_tool(tool_name)
        if not tool:
            results.append({"tool": tool_name, "success": False, "error": f"未知工具: {tool_name}"})
            continue
        try:
            validated = tool.validate_params(params) if tool.param_model else params
            result = await tool.execute(**validated)
            results.append({"tool": tool_name, "success": result.get("success", True), "data": result})
        except Exception as e:
            results.append({"tool": tool_name, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r.get("success"))
    return success_response(data={
        "results": results,
        "total": len(request.tasks),
        "success_count": success_count,
    })
