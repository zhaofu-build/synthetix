# Harness 参考优化方案

基于 Claude Code Harness 设计模式，对本项目 Agent 架构进行审计，按优先级整理可落地的优化项。

---

## P0 — 安全与稳定性（必须修复）

### 1. 权限模型已声明但未执行

**现状**：`tool_registry.py` 中工具注册了 `permission: "read_only"/"modify"/"destructive"`，但 `react_agent.py` 的 `_execute_tool()` 从未检查该字段。`delete_material` 等破坏性工具直接执行，无需确认。

**Harness 参考**：Claude Code 的 Deny → Ask → Allow 三级权限门控，每个工具调用都经过权限评估。

**优化方案**：

```python
# react_agent.py _execute_tool() 中添加权限检查
async def _execute_tool(self, tool_name, params, session_id=None):
    tool = registry.get_tool(tool_name)
    if not tool:
        return {"success": False, "error": f"工具 {tool_name} 不存在"}

    # 新增：权限门控
    if tool.permission in ("modify", "destructive"):
        # SSE 流式推送确认请求
        yield {"type": "tool_confirm", "tool": tool_name, "permission": tool.permission}
        confirmed = await self._wait_for_user_confirmation()
        if not confirmed:
            return {"success": False, "error": "用户取消了操作"}

    # ... 原有执行逻辑
```

### 2. 工具和 LLM 调用缺少超时

**现状**：`_execute_tool()` 和 `generate_response_async()` 都没有超时保护。一个卡死的 FFmpeg 进程或挂起的 LLM 调用会阻塞整个 Agent 循环。

**优化方案**：

```python
# 工具执行超时
import asyncio

TOOL_TIMEOUTS = {
    "default": 120,       # 默认 2 分钟
    "download_video": 300, # 下载 5 分钟
    "stabilize_video": 600 # 稳定化 10 分钟
}

async def _execute_tool(self, tool_name, params, **kwargs):
    timeout = TOOL_TIMEOUTS.get(tool_name, TOOL_TIMEOUTS["default"])
    try:
        result = await asyncio.wait_for(
            self._execute_tool_inner(tool_name, params, **kwargs),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        return {"success": False, "error": f"工具 {tool_name} 执行超时（{timeout}s）"}

# LLM 调用超时
LLM_TIMEOUT = 180  # 3 分钟

response_text = await asyncio.wait_for(
    generate_response_async(messages, provider_options=provider_options),
    timeout=LLM_TIMEOUT
)
```

### 3. API Key 泄露在 Git 追踪文件中

**现状**：`config/settings.json` 被 git 追踪且包含真实 API Key（`cn-b405176f...`）。

**优化方案**：

```bash
# 1. 将 settings.json 加入 .gitignore
echo "config/settings.json" >> .gitignore

# 2. 从 git 追踪中移除（保留本地文件）
git rm --cached config/settings.json

# 3. 创建 settings.local.json（已 git-ignored）存放敏感配置
```

---

## P1 — 架构健壮性

### 4. 统一配置系统

**现状**：项目存在三套独立配置系统且互不集成：
- `config_manager.py`：JSON 文件 + 深度合并 + 热重载
- `config_util.py`：`importlib` 重载 `config.py` 模块
- `src/config.py`：`os.getenv()` 模块级全局变量

`main.py` lifespan 手动桥接三个 key，新增配置容易遗漏。

**Harness 参考**：Claude Code 的 Settings 层级——env > settings.local > settings > defaults，统一合并为单一配置对象。

**优化方案**：

```python
# 统一配置加载器
class UnifiedConfig:
    """单例配置，合并优先级：env > settings.local.json > settings.json > default.json"""

    def __init__(self):
        self._data = {}
        self._load_defaults()
        self._load_settings()
        self._load_local_settings()
        self._load_env_overrides()

    def get(self, key: str, default=None):
        """点分路径访问：get('core_nexus.api_key')"""
        keys = key.split('.')
        value = self._data
        for k in keys:
            value = value.get(k, {}) if isinstance(value, dict) else default
            if value is default:
                return default
        return value

    def reload(self):
        """热重载，不重启服务"""
        self.__init__()
```

将 `src/config.py` 的模块级变量改为从 `UnifiedConfig` 读取，消除手动桥接。

### 5. 资源取消与清理

**现状**：SSE 客户端断连时，`react_agent.py` 中 `asyncio.ensure_future` 启动的工具任务继续运行。没有 `finally` 块取消待处理任务。

**优化方案**：

```python
async def process_message_stream(self, user_input, session_id, **kwargs):
    pending_tasks = set()
    try:
        async for event in self._taor_loop_stream(user_input, session_id, **kwargs):
            # 跟踪所有后台任务
            if event.get("type") == "tool_start":
                task = event.get("_task")
                if task:
                    pending_tasks.add(task)
            yield event
    except asyncio.CancelledError:
        # 客户端断连，取消所有进行中的工具任务
        for task in pending_tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*pending_tasks, return_exceptions=True)
        # 清理临时文件
        self._cleanup_orphaned_temp_files(session_id)
```

### 6. API 错误处理统一化

**现状**：几乎所有 API 端点都用 `try/except Exception → error_response()` 模式，绕过了已定义好的 `BusinessException`/`DatabaseException` 层次结构。

**Harness 参考**：Claude Code 用全局异常处理器捕获特定异常类型，端点只抛异常不构造响应。

**优化方案**：

```python
# 端点改为抛出类型化异常
@router.put("/projects/{project_id}")
async def update_project(project_id: int, data: ProjectUpdate, db=Depends(get_db)):
    project = db.query(VideoProject).filter(VideoProject.id == project_id).first()
    if not project:
        raise ResourceNotFoundException("Project", project_id)  # 替代手动 error_response
    # ... 更新逻辑

# 全局异常处理器自动处理（已有 exception_handlers.py）
```

---

## P2 — Agent 智能化

### 7. 上下文压缩（Context Compaction）

**现状**：`react_agent.py` 简单截断到最近 20 条消息，丢失早期上下文。

**Harness 参考**：Claude Code 自动压缩旧对话为摘要，保留关键信息。

**优化方案**：

```python
async def _compact_history(self, messages: list, max_messages: int = 20) -> list:
    """智能压缩历史消息，保留最近 N 条 + 摘要"""
    if len(messages) <= max_messages:
        return messages

    # 保留最近 10 条完整消息
    recent = messages[-10:]
    older = messages[:-10]

    # 用 LLM 生成摘要
    summary_prompt = [
        {"role": "system", "content": "请将以下对话历史压缩为简洁摘要，保留关键决策、用户偏好和工具调用结果。"},
        *older,
        {"role": "user", "content": "请生成摘要"}
    ]
    summary = await generate_response_async(summary_prompt, model=self.fast_model)

    return [
        {"role": "system", "content": f"[历史摘要] {summary}"},
        *recent
    ]
```

### 8. 记忆相关性评分

**现状**：`project_memory.py` 将所有偏好等权注入 prompt，无衰减、无筛选。

**Harness 参考**：Claude Code 的 Memory 系统按相关性评分加载 top-K 条目。

**优化方案**：

```python
def get_relevant_preferences(self, current_query: str, top_k: int = 5) -> list:
    """根据当前查询相关性返回 top-K 偏好"""
    scored = []
    for pref_key, pref_value in self.preferences.items():
        score = self._compute_relevance(pref_key, pref_value, current_query)
        # 时间衰减：30 天半衰期
        age_days = (datetime.now() - pref_value.get("updated_at", datetime.now())).days
        decay = 0.5 ** (age_days / 30)
        scored.append((pref_key, score * decay))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:top_k]
```

### 9. MCP 客户端健壮性

**现状**：MCP 服务器下线后仍注册，无重连、无健康检查、无连接池（每次调用新建 `httpx.AsyncClient`）。

**优化方案**：

```python
class MCPClient:
    def __init__(self):
        self._clients: Dict[str, httpx.AsyncClient] = {}  # 连接池
        self._health_status: Dict[str, bool] = {}
        self._tool_cache_ttl = 300  # 5 分钟缓存

    async def _ensure_client(self, server_name: str) -> httpx.AsyncClient:
        if server_name not in self._clients or self._clients[server_name].is_closed:
            server = self._servers[server_name]
            self._clients[server_name] = httpx.AsyncClient(
                base_url=server["url"],
                timeout=httpx.Timeout(60.0),
            )
        return self._clients[server_name]

    async def health_check(self):
        """定期检查所有 MCP 服务器健康状态"""
        for name, server in self._servers.items():
            try:
                client = await self._ensure_client(name)
                resp = await client.get("/health", timeout=5.0)
                self._health_status[name] = resp.status_code == 200
            except Exception:
                self._health_status[name] = False

    def get_tools_description(self) -> str:
        # 只返回健康服务器的工具
        healthy_tools = [
            desc for name, desc in self._tools.items()
            if self._health_status.get(name, False)
        ]
        return "\n".join(healthy_tools)
```

---

## P3 — 运维可观测性

### 10. 结构化日志与指标

**现状**：`react_agent.py` 中有 10+ 处 `print()` 语句，日志无结构化字段，无法做指标聚合。

**优化方案**：

```python
import structlog
import time

logger = structlog.get_logger()

async def _execute_tool(self, tool_name, params, **kwargs):
    start = time.monotonic()
    try:
        result = await tool.execute(**params)
        duration = time.monotonic() - start
        logger.info("tool_executed",
                     tool=tool_name,
                     duration_ms=round(duration * 1000),
                     success=result.get("success", True),
                     permission=tool.permission)
        return result
    except Exception as e:
        duration = time.monotonic() - start
        logger.error("tool_failed",
                      tool=tool_name,
                      duration_ms=round(duration * 1000),
                      error=str(e))
        raise
```

### 11. 优雅关闭

**现状**：`main.py` shutdown 块不关闭数据库连接、不取消后台任务、不排空进行中的请求。

**优化方案**：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... startup ...

    yield

    # Shutdown
    logger.info("开始优雅关闭...")

    # 1. 取消后台任务
    for task in background_tasks:
        task.cancel()
    await asyncio.gather(*background_tasks, return_exceptions=True)

    # 2. 关闭 MCP 连接
    await mcp_client.close_all()

    # 3. 关闭数据库
    from infrastructure.db.session import engine
    await engine.dispose()

    # 4. 关闭 CoreNexus 客户端
    await core_nexus_client.close()

    logger.info("优雅关闭完成")
```

### 12. 过期会话自动清理

**现状**：`session_manager.py` 的 `cleanup_expired_sessions()` 方法存在但从未被自动调用。

**优化方案**：

```python
# main.py lifespan 中添加定时任务
async def periodic_cleanup():
    while True:
        await asyncio.sleep(3600)  # 每小时清理一次
        try:
            session_manager.cleanup_expired_sessions()
            logger.info("过期会话清理完成")
        except Exception as e:
            logger.error(f"会话清理失败: {e}")

# lifespan startup 中
cleanup_task = asyncio.create_task(periodic_cleanup())
```

---

## 优化优先级总览

| 优先级 | 项目 | 工作量 | 影响 |
|--------|------|--------|------|
| **P0** | 权限执行 | 小 | 安全：防止误删/误改 |
| **P0** | 执行超时 | 小 | 稳定性：防止 Agent 卡死 |
| **P0** | API Key 脱离 git | 极小 | 安全：防止密钥泄露 |
| **P1** | 统一配置 | 中 | 维护性：消除三套配置桥接 |
| **P1** | 资源取消清理 | 中 | 稳定性：防止资源泄漏 |
| **P1** | 错误处理统一 | 中 | 可维护性：消除数百行重复代码 |
| **P2** | 上下文压缩 | 中 | 智能：长对话不丢上下文 |
| **P2** | 记忆相关性 | 小 | 智能：prompt 更精准 |
| **P2** | MCP 健壮性 | 小 | 可靠性：外部服务降级 |
| **P3** | 结构化日志 | 小 | 运维：可观测、可排查 |
| **P3** | 优雅关闭 | 小 | 运维：无残留进程 |
| **P3** | 会话自动清理 | 极小 | 运维：磁盘/DB 不膨胀 |

---

## 与 Harness 的对应关系

| Claude Code Harness | 本项目对应 | 优化方向 |
|---------------------|-----------|---------|
| Permission Gating | `tool.permission` 声明 | 添加运行时执行检查 |
| Tool Timeout | 无 | 添加 `asyncio.wait_for` |
| Lifecycle Hooks | `before_execute/after_execute` | 完善 `on_agent_start/end` |
| Context Compaction | 截断到 20 条 | LLM 摘要 + 保留关键信息 |
| Settings Hierarchy | 三套独立系统 | 统一为单一配置源 |
| Memory Relevance | 等权注入 | 相关性评分 + 时间衰减 |
| Graceful Shutdown | 不完整 | 添加资源释放和请求排空 |
| Structured Logging | print() + 无结构日志 | structlog + 指标聚合 |
