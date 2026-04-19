"""
MCP 管理 API

提供 MCP Server 的注册、发现、调用接口。
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel
from fastapi import APIRouter

from src.shared.models.response import success_response, error_response
from src.agent.mcp_client import mcp_client

router = APIRouter()


class MCPServerRequest(BaseModel):
    name: str
    url: str


class MCPCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any] = {}


@router.get("/servers", summary="列出 MCP Server")
async def list_servers():
    return success_response(data=mcp_client.list_servers())


@router.post("/servers", summary="注册 MCP Server")
async def register_server(req: MCPServerRequest):
    mcp_client.register_server(req.name, req.url)
    tools = await mcp_client.discover_tools(req.name)
    return success_response(data={
        "server": req.name,
        "tools_count": len(tools),
        "tools": [{"name": t.name, "description": t.description} for t in tools],
    })


@router.delete("/servers/{name}", summary="移除 MCP Server")
async def remove_server(name: str):
    mcp_client.remove_server(name)
    return success_response(message=f"已移除 {name}")


@router.post("/call", summary="调用 MCP 工具")
async def call_tool(req: MCPCallRequest):
    result = await mcp_client.call_tool(req.tool_name, req.arguments)
    return success_response(data=result)


@router.get("/tools", summary="列出所有 MCP 工具")
async def list_tools():
    tools = [{"name": t.name, "description": t.description} for t in mcp_client.tools.values()]
    return success_response(data={"tools": tools, "count": len(tools)})
