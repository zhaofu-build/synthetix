"""
MCP（Model Context Protocol）客户端

支持外部工具通过 MCP 协议动态接入 Agent。
支持 SSE/HTTP 传输（远程 MCP Server）。
连接池复用 + 健康检查 + 自动降级。
"""
import json
import logging
from typing import Dict, List, Any
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
    """MCP 协议客户端（连接池 + 健康检查）"""

    def __init__(self):
        self.servers: Dict[str, str] = {}  # name -> url
        self.tools: Dict[str, MCPTool] = {}
        self._clients: Dict[str, httpx.AsyncClient] = {}
        self._health: Dict[str, bool] = {}

    async def _ensure_client(self, server_name: str) -> httpx.AsyncClient:
        """获取或创建持久连接"""
        if server_name in self._clients and not self._clients[server_name].is_closed:
            return self._clients[server_name]

        url = self.servers.get(server_name)
        if not url:
            raise ValueError(f"MCP Server '{server_name}' 未注册")

        client = httpx.AsyncClient(
            base_url=url.rstrip('/'),
            timeout=httpx.Timeout(60.0, connect=10.0),
        )
        self._clients[server_name] = client
        return client

    def register_server(self, name: str, url: str):
        """注册 MCP Server"""
        self.servers[name] = url.rstrip('/')
        # 关闭旧连接（URL 可能变更）
        old = self._clients.pop(name, None)
        if old and not old.is_closed:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(old.aclose())
            except Exception:
                pass
        logger.info(f"注册 MCP Server: {name} -> {url}")

    def remove_server(self, name: str):
        """移除 MCP Server"""
        self.servers.pop(name, None)
        self.tools = {n: t for n, t in self.tools.items() if not n.startswith(f"{name}.")}
        self._health.pop(name, None)
        old = self._clients.pop(name, None)
        if old and not old.is_closed:
            import asyncio
            try:
                asyncio.get_event_loop().create_task(old.aclose())
            except Exception:
                pass

    async def discover_tools(self, server_name: str) -> List[MCPTool]:
        """从 MCP Server 发现可用工具"""
        if server_name not in self.servers:
            return []

        try:
            client = await self._ensure_client(server_name)
            resp = await client.get("/tools", timeout=10.0)
            resp.raise_for_status()
            data = resp.json()

            tools = []
            for tool_data in data.get("tools", []):
                tool = MCPTool(
                    name=f"{server_name}.{tool_data['name']}",
                    description=tool_data.get("description", ""),
                    parameters=tool_data.get("parameters", {}),
                    server_url=self.servers[server_name],
                )
                tools.append(tool)
                self.tools[tool.name] = tool

            self._health[server_name] = True
            logger.info(f"MCP Server '{server_name}' 发现 {len(tools)} 个工具")
            return tools

        except Exception as e:
            self._health[server_name] = False
            logger.error(f"MCP 工具发现失败 ({server_name}): {e}")
            return []

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """调用 MCP 工具"""
        tool = self.tools.get(tool_name)
        if not tool:
            return {"success": False, "error": f"MCP 工具不存在: {tool_name}"}

        server_name = tool_name.split('.', 1)[0]

        try:
            client = await self._ensure_client(server_name)
            resp = await client.post(
                f"/tools/{tool_name.split('.', 1)[1]}",
                json={"arguments": arguments},
            )
            resp.raise_for_status()
            self._health[server_name] = True
            return resp.json()

        except Exception as e:
            self._health[server_name] = False
            logger.error(f"MCP 工具调用失败 ({tool_name}): {e}")
            return {"success": False, "error": str(e)}

    async def health_check(self):
        """检查所有 MCP Server 健康状态"""
        for name in self.servers:
            try:
                client = await self._ensure_client(name)
                resp = await client.get("/health", timeout=5.0)
                self._health[name] = resp.status_code == 200
            except Exception:
                self._health[name] = False

    def get_tools_description(self) -> str:
        """获取所有健康 MCP Server 的工具描述"""
        if not self.tools:
            return ""

        # 按服务器分组，只返回健康的
        healthy_tools = []
        for name, tool in self.tools.items():
            server_name = name.split('.', 1)[0]
            if self._health.get(server_name, True):  # 未检查过默认为健康
                params_str = ", ".join(tool.parameters.get("properties", {}).keys())
                healthy_tools.append(f"- {name}: {tool.description} (参数: {params_str})")

        if not healthy_tools:
            return ""

        return "## MCP 外部工具\n" + "\n".join(healthy_tools)

    def list_servers(self) -> List[Dict[str, Any]]:
        """列出已注册的 MCP Server 及健康状态"""
        return [
            {
                "name": name,
                "url": url,
                "healthy": self._health.get(name, None),
            }
            for name, url in self.servers.items()
        ]

    async def close_all(self):
        """关闭所有连接池"""
        for name, client in self._clients.items():
            if not client.is_closed:
                try:
                    await client.aclose()
                except Exception:
                    pass
        self._clients.clear()
        logger.info("MCP 连接池已关闭")


# 全局单例
mcp_client = MCPClient()
