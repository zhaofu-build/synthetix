# Synthetix 项目全面优化分析报告

> 分析日期：2026-05-10

## 一、安全问题（CRITICAL）

### 1. 无任何 API 认证/授权
- **所有端点**完全无认证（`agent_api.py`, `tool_api.py`, `mcp_api.py` 等全部 API 文件）
- `AuthenticationException` 已定义但从未使用
- 最危险端点：
  - `PATCH /api/tools/config` — 无限制修改系统配置（含 API Key）
  - `POST /api/agent/execute` — 任意工具执行
  - `POST /api/mcp/servers` — 任意 URL 注册（SSRF 风险）

### 2. 敏感信息泄露
- `config/settings.json.bak` 含真实 API Key，**未被 `.gitignore` 覆盖**（当前只忽略 `config/settings.json`，不匹配 `.bak`）
- API 响应暴露服务器本地文件路径（`tool_api.py:39,107`）
- 异常消息直接暴露内部信息（9+ 处 `str(e)` 返回给客户端）
- `/health` 端点暴露系统资源信息（CPU、内存、GPU、磁盘）

### 3. 无速率限制
- `RateLimitException` 已定义但从未使用
- AI 服务端点（LLM/TTS/VL）无任何调用限制，存在费用风险

### 4. 文件上传安全
- 6 个上传端点无文件大小限制（`comic_api.py:235`, `project_api.py:101,297`, `core_nexus_api.py:252,307,393`）
- 上传文件扩展名无白名单校验（`comic_api.py:231`, `project_api.py:97`）
- 多个端点接受用户提供的文件路径直接传给 FFmpeg（`video_api.py:136,161,174,186,253`）

---

## 二、测试（CRITICAL）

### 5. 全部单元测试已损坏
所有 4 个测试文件的 import 路径过时（模块已重构但测试未更新）：
- `test_repository.py` — 引用 `src.repository`（应为 `src.infrastructure.repositories`）
- `test_services.py` — 引用 `src.service`（应为 `src.application.services`）
- `test_file_util.py` — 引用 `src.util`（应为 `src.shared.utils`）
- `test_request.py` / `test_response.py` — 引用 `src.model`（应为 `src.shared.models`）

### 6. 测试覆盖极低
- 整个 `agent/` 子系统无任何测试
- `ffmpeg_adapter.py`（最复杂模块）无测试
- 所有 API 路由无集成测试
- 无 WebSocket 测试
- `pytest.ini` 设定 `--cov-fail-under = 60`，实际覆盖率可能 < 20%

---

## 三、前端架构（HIGH）

### 7. 上帝组件
| 组件 | 行数 | 问题 |
|------|------|------|
| `VideoStitching.vue` | 1,618 | 项目CRUD + 素材 + AI + 方案 + TTS + 语音 + BGM + 渲染 |
| `ComicDrama.vue` | 1,254 | 系列 + 章节 + 角色 + 分镜 + 脚本 + 图片 + 音频 + BGM |
| `MaterialsPanel.vue` | 1,038 | 网格 + 搜索 + 上传 + AI分析 + 编辑 + 标签 + 拖拽 |

### 8. 大量重复代码
- 聊天逻辑在 4 处重复实现（`project.js`, `AIClip.vue`, `LLMChat.vue`, `ChatSidebar.vue`）
- 项目 CRUD 在 3 处重复（`VideoStitching.vue`, `AIClip.vue`, `ComicDrama.vue`）
- BGM 管理在 3 处重复
- 63 处 raw `fetch()` 调用绕过统一 API 层

### 9. 内存泄漏
- `PreviewPanel.vue` — `setInterval` 在组件卸载时未清理（`onUnmounted` 已导入但未使用）
- `WorkspacePanel.vue` — `mousemove` 监听器未在卸载时移除
- `TimelineRuler.vue` — 无 `onUnmounted` 钩子，事件监听器泄漏
- `VideoStitching.vue` / `ComicDrama.vue` — `_saveTimers` debounce 定时器未清理

### 10. 双请求系统
- `src/api/request.js`（Axios）和 `src/utils/request.js`（fetch）并存
- stores 和组件直接用 `fetch()` 绕过 Axios 拦截器，导致错误处理不一致、loading 状态失效

### 11. i18n 基本未生效
- 80-90% 的用户界面字符串硬编码中文
- `en-US.js` 存在但实际组件几乎不调用 `$t()`
- 关键页面：`VideoStitching.vue`, `ComicDrama.vue`, `ChatSidebar.vue`, `MainLayout.vue` 全部硬编码

---

## 四、Agent 系统（HIGH）

### 12. 会话内存泄漏
- `session_manager.py:87` — `_sessions` 字典无上限增长，`cleanup_expired_sessions` 存在但从未自动调用
- `knowledge_base.py:347` — `_kbs` 字典无上限缓存
- `AgentConfig.SESSION_CLEANUP_INTERVAL` 已定义但未使用

### 13. 子 Agent 无超时
- `multi_agent.py:89,132` — 子 Agent LLM 调用无 `asyncio.wait_for` 包装，可能无限挂起
- `multi_agent.py:178-214` — `run_pipeline_parallel` 名字误导，实际是串行执行

### 14. 工具调用解析脆弱
- `react_agent.py:1293` 和 `multi_agent.py:93` — 相同正则重复定义（违反 DRY）
- JSON 解析失败静默返回 `{}` 而非告知 LLM 修正
- 无法处理嵌套、空格变体等边缘情况

### 15. 多个工具缺少参数校验
- `image_to_video` — `duration` 无范围校验，负值或极大值可导致 FFmpeg 挂起
- `split_video` — `interval` 无最小值检查，0 会导致无限分割
- `add_text_overlay` — FFmpeg drawtext 注入防护不足（`{`, `%` 未过滤）
- 约 40+ 工具缺少 Pydantic 参数模型

### 16. LLM 调用无重试
- `react_agent.py:1105-1114` — LLM 超时直接杀死整个请求
- `MAX_ACTION_RETRIES` 和 `MAX_LLM_PARSE_RETRIES` 常量已定义但从未使用
- MCP 客户端超时后标记服务器不健康，无自动恢复

### 17. 向量索引不持久化
- `knowledge_base.py:98` — `SimpleVectorIndex` 重启后丢失所有向量数据
- BM25 每次搜索重新分词所有文档（O(N*M)），无可扩展性

---

## 五、数据库（MEDIUM）

### 18. 缺少级联删除
- 删除项目 → 孤立的 `ClipPlanItem` 记录
- 删除视频源 → 孤立的 `VideoShot` 记录
- 所有 ForeignKey 均未配置 `cascade` 或 `passive_deletes`

### 19. 缺少索引
- `DialogSession.status`, `current_video_id` 无索引
- `AudioSource.audio_name`, `seed` 无索引
- `VideoSource.file_type` 无索引
- `ComicProject.series_id`, `status` 无索引

### 20. N+1 查询
- `render_service.py:96-125` — 每个片段单独打开数据库会话
- `base_repository.py` — `update()` 和 `soft_delete()` 先 `get_by_id()` 再操作

### 21. SQLite 并发限制
- `check_same_thread=False` 存在写锁风险
- 无连接池配置（`pool_size`, `max_overflow`）
- 数据库路径硬编码 Windows 路径，Docker 中不可用

---

## 六、基础设施（MEDIUM）

### 22. FFmpeg 临时文件泄漏
- `ffmpeg_adapter.py` `add_subtitle()` — 异常时 SRT/ASS 临时文件未清理（不在 `finally` 块中）
- 渲染进程崩溃后帧目录残留
- 无磁盘空间预检

### 23. Docker 部署问题
- 容器以 root 运行（无 `USER` 指令）
- 无多阶段构建（Node.js 构建工具留在最终镜像）
- `main.py` 硬编码 `HF_HOME = 'D:/hf-model'`（Windows 路径在 Linux 容器中失效）
- 无 `.dockerignore` 排除 `venv/`、`synthetix-tauri/`

### 24. 配置管理
- `config_manager.py` 无并发锁保护（`_merged` 字典读写竞争）
- 无配置值校验（URL 格式、API Key 非空、端口范围）
- 时间列类型不一致（`TIMESTAMP` vs `DateTime`）

### 25. 日志与可观测性
- 无结构化日志（纯文本格式，无 trace ID）
- 指标文件 `ai_calls.jsonl` 无轮转，无限增长
- 无 HTTP 请求日志中间件（延迟、状态码）

---

## 七、前端性能（MEDIUM）

### 26. 打包优化
- Element Plus 全量导入（`main.js:47`），未配置 tree-shaking
- `vite.config.js:36` — 生产环境始终启用 sourcemap
- `unplugin-vue-components` 在 devDependencies 中但未配置使用

### 27. 渲染性能
- `ChatSidebar.vue` — SSE 每次追加内容触发所有消息重渲染
- `UnifiedEditor.vue` — 项目列表按时间分组，每次重新计算遍历 3 遍
- 列表无分页 UI（项目、素材、语音均硬编码 `page_size` 限制）

### 28. 竞态条件
- `project.js:238` — `processChatMessage` 不取消活跃的 SSE 流，可能同时更新消息数组
- `MaterialsPanel.vue` — 批量操作无并发保护，双击可触发重复操作
- 文件上传和渲染等长时操作无取消机制

---

## 八、代码质量（LOW）

### 29. 后端
- `error_response()` 返回 HTTP 200 + body 中 code 500（非正确状态码）
- `comic_api.py:361` — 同步处理函数内调用 `run_until_complete`
- `constants.py:192-193` — `MAX_ACTION_RETRIES` 等常量定义但未使用
- `core_nexus_api.py` 多处 `**kwargs` 解包用户输入

### 30. 前端
- `project.js` — `planLoading` 重复声明（line 66 和 line 82）
- `PreviewPanel.vue` — 多个未使用的函数和 ref（`color`, `hoverTime`, `getClipWidth`, `onTimelineClick`）
- 前端同时检查 `row.videoName` 和 `row.video_name`（`MaterialsPanel.vue`），说明后端转换不一致
- 4 处 `v-html` 使用（`AIClip.vue`, `LLMChat.vue`, `ChatSidebar.vue`, `VL.vue`）

---

## 优化优先级建议

| 优先级 | 类别 | 建议行动 |
|--------|------|----------|
| **P0** | 安全 | 添加 API 认证中间件；修复 `settings.json.bak` gitignore |
| **P0** | 测试 | 修复所有测试 import 路径，确保 CI 可运行 |
| **P1** | 前端 | 拆分上帝组件，统一请求层，修复内存泄漏 |
| **P1** | Agent | 添加会话自动清理，子 Agent 超时，LLM 重试 |
| **P1** | 数据库 | 添加级联删除和缺失索引 |
| **P2** | 安全 | 添加速率限制，文件上传校验，路径白名单 |
| **P2** | 基础设施 | Docker 多阶段构建，结构化日志，配置校验 |
| **P3** | 性能 | Element Plus tree-shaking，关闭生产 sourcemap |
| **P3** | i18n | 逐步提取硬编码中文字符串 |
| **P3** | 代码质量 | 统一错误处理模式，清理死代码 |
