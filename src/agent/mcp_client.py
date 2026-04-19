"""
MCP（Model Context Protocol）客户端

支持外部工具通过 MCP 协议动态接入 Agent。
支持 SSE/HTTP 传输（远程 MCP Server）。
"""
import json
import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    parameters: Dict[str, Any]
    server_url: str


class MCPClient:
    """MCP 协议客户端"""

    def __init__(self):
        self.servers: Dict[str, str] = {}  # name -> url
        self.tools: Dict[str, MCPTool] = {}

    def register_server(self, name: str, url: str):
        """注册 MCP Server"""
        self.servers[name] = url.rstrip('/')
        logger.info(f"注册 MCP Server: {name} -> {url}")

    def remove_server(self, name: str):
        """移除 MCP Server"""
        self.servers.pop(name, None)
        self.tools = {n: t for n, t in self.tools.items() if not n.startswith(f"{name}.")}

    async def discover_tools(self, server_name: str) -> List[MCPTool]:
        """从 MCP Server 发现可用工具"""
        url = self.servers.get(server_name)
        if not url:
            return []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/tools")
                resp.raise_for_status()
                data = resp.json()

            tools = []
            for tool_data in data.get("tools", []):
                tool = MCPTool(
                    name=f"{server_name}.{tool_data['name']}",
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                    server_url=url,
                )
                tools.append(tool)
                self.tools[tool.name] = tool

            logger.info(f"MCP Server '{server_name}' 发现 {len(tools)} 个工具")
            return tools

        except Exception as e:
            logger.error(f"MCP 工具发现失败 ({server_name}): {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"MCP 工具不存在: {tool_name}"}

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    f"{tool.server_url}/tools/{tool_name.split('.', 1)[1]}",
                    json={"arguments": arguments},
                )
                resp.raise_for_status()
                return resp.json()

        except Exception as e:
            logger.error(f"MCP 工具调用失败 ({tool_name}): {e}")
            return {"success": False, "error": str(e)}

    def get_tools_description(self) -> str:
        """获取所有 MCP 工具描述（供 Agent 提示词使用）"""
        if not self.tools:
            return ""
        parts = ["## MCP 外部工具"]
        for tool in self.tools.values():
            params_str = ", ".join(tool.parameters.get("properties", {}).keys())
            parts.append(f"- {tool.name}: {tool.description} (参数: {params_str})")
        return "\n".join(parts)

    def list_servers(self) -> List[Dict[str, str]]:
        """列出已注册的 MCP Server"""
        return [{"name": name, "url": url} for name, url in self.servers.items()]


# 全局单例
mcp_client = MCPClient()
