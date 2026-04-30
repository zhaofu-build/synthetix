# 04 - MCP 协议

## 概述

MCP（Model Context Protocol）是 Claude Code 的核心工具协议，实现了模型与外部工具的**安全双向通信**。它定义了一套标准化的工具接入规范，使 Claude Code 能无缝连接外部工具生态。通信采用 **JSON-RPC over WebSocket/Stdio** 标准。

## 协议架构

### 三个核心角色

| 角色 | 说明 | 实例 |
|------|------|------|
| **宿主（Host）** | LLM 应用，管理客户端 | Claude Desktop、Claude Code |
| **客户端（Client）** | 维护与服务器一对一连接的协议连接器 | `MCPConnector` 子类 |
| **服务器（Server）** | 暴露工具、数据源的轻量级程序 | 第三方 MCP Server |

```
Host（Claude Code）
  ├── Client 1 ←→ MCP Server A（数据库查询工具）
  ├── Client 2 ←→ MCP Server B（文件管理工具）
  └── Client 3 ←→ MCP Server C（API 调用工具）
```

### 协议组件

- **上下文管理器（Context Manager）**：负责收集和处理代码上下文
- **模式定义（Schema Definition）**：标准化信息格式化方式
- **连接器（Connector）**：实现不同系统间的通信适配

## 通信格式

### JSON-RPC 2.0 请求

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "tool": "toolName",
    "args": { "key": "value" }
  },
  "id": 12345
}
```

### JSON-RPC 2.0 响应

```json
{
  "jsonrpc": "2.0",
  "result": {
    "content": "工具执行结果",
    "isError": false
  },
  "id": 12345
}
```

## 传输通道

| 通道 | 适用场景 | 特点 |
|------|----------|------|
| **stdio** | 简单工具调用 | 子进程标准输入输出，低延迟 |
| **HTTP API** | 需要长连接或复杂交互 | 支持 REST 风格调用 |
| **Server-Sent Events (SSE)** | 流式响应 | 服务器主动推送，适合实时数据 |

## 连接器实现

### MCPConnector 基类

```typescript
import { MCPConnector, ConnectorConfig } from '@anthropic/mcp-connectors';

class WebFetchConnector extends MCPConnector {
  constructor(config: ConnectorConfig) {
    super(config);
  }

  async fetchData(query: string): Promise<any> {
    const response = await fetch('https://api.example.com/data?q=' + encodeURIComponent(query));
    return response.json();
  }

  async processContext(data: any): Promise<Context> {
    // 将原始数据转换为模型可理解的上下文
    return this.formatAsContext(data);
  }
}
```

### MCPService 核心服务

```typescript
class MCPService {
  private connections: Map<string, MCPConnection>;
  private toolRegistry: Map<string, MCPToolDefinition>;

  // 连接到 MCP 服务器
  async connectToMCP(serverConfig: MCPConfig): Promise<void> {
    const connection = new MCPConnection(serverConfig);
    await connection.initialize();
    this.connections.set(serverConfig.name, connection);
    // 注册服务器提供的工具
    const tools = await connection.listTools();
    tools.forEach(tool => this.toolRegistry.set(tool.name, tool));
  }

  // 通过 MCP 调用工具
  async callToolOverMCP(toolName: string, params: any): Promise<any> {
    const request = {
      jsonrpc: "2.0",
      method: "tools/call",
      params: { tool: toolName, args: params },
      id: Date.now()
    };
    return await this.sendRequest(request);
  }
}
```

## MCP 方法一览

| 方法 | 功能 | 方向 |
|------|------|------|
| `tools/list` | 列出可用工具 | Client → Server |
| `tools/call` | 执行工具调用 | Client → Server |
| `resources/list` | 列出可用资源 | Client → Server |
| `resources/read` | 读取资源 | Client → Server |
| `resources/write` | 写入资源 | Client → Server |
| `prompts/list` | 列出可用提示模板 | Client → Server |
| `memory/access` | 访问记忆 | Client → Server |
| `agent/create` | 创建 Agent | Client → Server |
| `agent/send` | 发送 Agent 消息 | Client → Server |
| `completion/complete` | 获取补全建议 | Client → Server |

## 能力协商

MCP 客户端和服务器在建立连接时进行能力协商：

```typescript
interface MCPCapabilities {
  tools?: { listChanged: boolean };      // 支持工具列表动态变化
  resources?: { subscribe: boolean };     // 支持资源订阅
  prompts?: { listChanged: boolean };     // 支持提示模板动态变化
  logging?: {};                           // 支持日志
}
```

协商流程：
1. 客户端发送 `initialize` 请求，声明自身能力
2. 服务器响应自身能力
3. 双方根据交集确定可用功能
4. 连接建立完成

## 生命周期管理

```
创建连接 → 能力协商 → 就绪
                ↓
      正常使用（tools/call、resources/read 等）
                ↓
      ┌─ 正常关闭 → 发送 shutdown 通知
      └─ 异常断开 → 自动重连机制
```

### 连接池管理

```typescript
class MCPConnectionPool {
  private pool: Map<string, MCPConnection>;
  private maxConnections: number = 10;
  private idleTimeout: number = 30000; // 30秒空闲超时

  async acquire(serverName: string): Promise<MCPConnection> {
    // 复用空闲连接或创建新连接
  }

  async release(connection: MCPConnection): Promise<void> {
    // 归还连接到池中
  }
}
```

## 安全机制

### 调用前权限检查

所有 MCP 调用前需通过权限系统验证：

```
MCP 工具调用请求
  ↓
PermissionManager.hasPermission()     # 检查工具权限
  ↓
PathSanitizer.sanitize()              # 过滤路径参数
  ↓
Zod Schema 校验                       # 参数类型校验
  ↓
连接签名验证                          # 验证 MCP Server 身份
  ↓
执行调用
```

### 参数校验

通过 Zod Schema 确保输入参数类型安全：

```typescript
const mcpToolSchema = z.object({
  tool: z.string().min(1).max(100),
  args: z.record(z.any()),
  id: z.number()
});
```

### 沙箱执行

高危 MCP 工具在沙箱环境中执行，与主进程隔离。

## MCP 与内置工具的关系

MCP 外部工具与内置工具共享同一套接口和权限体系：

| 对比项 | 内置工具 | MCP 外部工具 |
|--------|----------|--------------|
| 注册方式 | `builtInTools.set()` | `MCPService.connectToMCP()` |
| 接口规范 | 实现 `ToolBase` | 实现 `MCPConnector` |
| 权限控制 | `PermissionManager` | `PermissionManager`（同一套） |
| Schema 校验 | Zod v4 | Zod v4 |
| 执行策略 | 并行/串行 | 并行/串行（同一套逻辑） |

**设计优势：** 对 Agent 来说，内置工具和 MCP 外部工具完全透明，统一通过 `ToolManager` 调用。

> **延伸阅读：**
> - 工具系统整体架构详见 [03-工具系统](03-工具系统.md)
> - 权限与安全详见 [06-权限与安全系统](06-权限与安全系统.md)
> - 插件系统的 MCP 通信详见 [09-插件与Hook系统](09-插件与Hook系统.md)
