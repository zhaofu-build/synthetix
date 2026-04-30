# Synthetix 项目优化分析报告

> 生成时间：2026-04-16 | 分析范围：后端 Python/FastAPI + 前端 Vue 3

---

## 目录

- [一、不可用功能（运行时必崩）](#一不可用功能运行时必崩)
- [二、功能缺失 / 未完成](#二功能缺失--未完成)
- [三、安全风险](#三安全风险)
- [四、性能问题](#四性能问题)
- [五、前端架构问题](#五前端架构问题)
- [六、后端架构问题](#六后端架构问题)
- [七、代码质量](#七代码质量)
- [八、UI / UX 问题](#八ui--ux-问题)
- [九、数据库问题](#九数据库问题)
- [十、优先级汇总](#十优先级汇总)

---

## 一、不可用功能（运行时必崩）

### 1.1 AudioService 缺少 db 参数 → TypeError

`AudioService.__init__` 要求 `db: Session` 参数，但两处调用未传入：

- `src/interfaces/api/project_api.py:284` → `AudioService()`
- `src/application/services/render_service.py:189` → `AudioService()`

**影响**：调用涉及音频的 API 端点时会抛 `TypeError`。

### 1.2 SoVits V4 导入路径错误 → ModuleNotFoundError

```python
# src/application/services/audio_service.py:301
from src.service.sovits_v4 import use_sovits_v4
```

`src/service/` 目录不存在。调用 `generate_sovits_tts()` 必崩。

### 1.3 LLMChat.vue 调用不存在的 SSE 端点

```javascript
// src/components/LLMChat.vue:97
fetch('/api/nexus/llm/stream')
```

后端无 `/api/nexus/llm/stream` 路由。LLM Chat 组件的流式对话功能完全不可用。

### 1.4 TTS.vue 使用相对路径调用 API

```javascript
// src/components/TTS.vue:137
fetch('/api/nexus/tts')
```

相对路径仅在前后端同源时可用。Vite 开发模式（9528 端口）下请求会 404。应使用 `aiApi.tts()` 统一模块。

---

## 二、功能缺失 / 未完成

### 2.1 日志读取接口为空壳

```python
# src/interfaces/api/tool_api.py:79
# TODO: 实现日志读取功能
return success_response(data="", message="获取日志成功")
```

前端"获取日志"功能始终返回空字符串。

### 2.2 渲染预览未实现

```python
# src/application/services/render_service.py:276-286
```

- `preview()` 文档说生成低分辨率预览，实际直接调用 `render_timeline()`，无差异化。
- `get_render_progress()` 始终返回 `{"progress": 0, "status": "pending"}`，渲染是同步的，前端永远看不到进度变化。

### 2.3 视频生成路由未注册

```python
# main.py:99
# app.include_router(video_generation_api, tags=["视频生成"])
```

该路由被注释，对应功能未启用。

### 2.4 配置更新仅缓存不持久化

```python
# src/shared/utils/file_util.py:197-201
logger.warning(f"配置项 {key} 已更新为 {value}（仅缓存，未持久化）")
```

前端"保存设置"API 返回成功，但重启后配置丢失。

### 2.5 ffmpeg 执行失败静默返回 None

```python
# src/application/services/ffmpeg_adapter.py:940-944
except subprocess.CalledProcessError as e:
    logger.error(...)
    # 隐式 return None
```

调用方不检查 None 就使用返回值，会导致下游 `AttributeError` / `TypeError`。

---

## 三、安全风险

### 3.1 [高] v-html XSS 注入

以下 4 处用 `v-html` 渲染 AI 输出，仅做了 `\n` → `<br>` 转换，无 HTML 消毒：

| 组件 | 行号 |
|------|------|
| `ChatSidebar.vue` | 12 |
| `AIClip.vue` | 84 |
| `LLMChat.vue` | 19 |
| `VL.vue` | 56 |

**修复**：引入 DOMPurify，或使用 Markdown 渲染器（如 `marked` + sanitizer）。

### 3.2 [高] Agent 工具路径穿越

```python
# src/agent/tool_registry.py:1143
target = path or config.UPLOAD_DIR  # path 来自 LLM 输出，无校验
```

`list_directory` 和 `search_files` 工具接受任意路径。LLM 被诱导时可遍历服务器任意目录。

### 3.3 [高] 文件上传无类型校验

`/api/videos`（上传视频）和 `/api/tools/upload/file`（通用上传）均未校验：
- 文件扩展名
- MIME 类型
- 文件内容

可上传 `.exe`、`.html` 等危险文件。

### 3.4 [中] 全部 API 端点无认证

所有接口（含删除、渲染等破坏性操作）完全开放，无认证中间件。

### 3.5 [低] API Key 泄露风险

```python
# src/application/services/video_downloader_adapter.py:93-94
headers = {"Authorization": api_key, ...}
```

请求失败时日志可能包含 headers，暴露 Pexels/Pixabay API Key。

---

## 四、性能问题

### 4.1 [高] 同步阻塞在 async 端点中

`core_nexus_api.py` 多处 async 端点调用同步方法，阻塞事件循环长达 120 秒：

| 行号 | 调用 |
|------|------|
| 88 | `client.llm_generate()` |
| 163 | `client.tts_generate()` |
| 209 | `client.asr_transcribe()` |
| 296 | `client.vl_generate()` |
| 402 | `client.text_to_music()` |

`CoreNexusClient` 已有 async 版本方法（如 `llm_generate_async()`），但 API 层未使用。

### 4.2 [高] 同步流式输出阻塞事件循环

```python
# src/interfaces/api/core_nexus_api.py:123-135
def generate():
    for chunk in client.llm_generate_stream(...):  # 同步 HTTP
```

在 `StreamingResponse` 中使用同步生成器，阻塞 asyncio 事件循环。VL 流式同理（line 321）。

### 4.3 [中] FFmpeg 操作阻塞事件循环

```python
# src/interfaces/api/video_api.py:101
async def process_video(...):
    result = video_service.process_video(...)  # subprocess.run, 可能数分钟
```

FFmpeg `subprocess.run` 是长时间阻塞调用，应使用 `asyncio.create_subprocess_exec` 或 `run_in_executor`。

### 4.4 [中] N+1 查询

```python
# src/agent/tool_registry.py:296-308
for vid in video_ids:
    if not repo.exists(vid):  # 每个视频一次 DB 查询
```

应改为 `WHERE id IN (...)` 批量查询。

### 4.5 [中] render_service 全表扫描做模糊匹配

```python
# src/application/services/render_service.py:235-240
videos = repo.get_active_videos()  # 加载全部
for v in videos:
    if v.video_name and material_id in v.video_name:  # Python 线性扫描
```

应改为数据库 `LIKE` 查询。

### 4.6 [中] refreshMaterials 串行请求

```javascript
// src/store/modules/project.js:327-342
await videoApi.getSourceVideos()        // 请求 1
await projectApi.getFull(projectId)     // 请求 2
```

两个独立请求应并行：`Promise.all([videoApi.getSourceVideos(), projectApi.getFull(id)])`。

### 4.7 [低] 每条 Agent 消息触发 DB 持久化

```python
# src/agent/react_agent.py:112
self.sessions.persist_session(state)  # 每轮 TAOR 循环都写 DB
```

高频对话时产生大量 DB 写入。可改为定时/定量批量持久化。

### 4.8 [低] Element Plus 全量引入

```javascript
// src/main.js:44
app.use(ElementPlus)  // ~800KB 未 tree-shake
```

应使用 `unplugin-vue-components` + `unplugin-auto-import` 按需引入。

---

## 五、前端架构问题

### 5.1 [高] 双 API 请求系统

项目存在两套完全独立的 HTTP 请求系统，互不连通：

| 系统 | 文件 | 用途 |
|------|------|------|
| Axios | `src/api/request.js` | API 模块（video, audio, ai, project） |
| fetch | `src/utils/request.js` | Pinia store、旧组件直接使用 |

**问题**：
- Store 中 chat/agent 请求绕过 Axios 拦截器（无统一错误处理）
- 两个系统的响应提取逻辑不同：Axios 返回 `data.data ?? data`，fetch 返回 `result.data || {}`
- 后端返回 `{ success: true, data: null }` 时，Axios 得 `null`，fetch 得 `{}`

### 5.2 [高] API_HOST 硬编码 × 2

```javascript
// src/utils/request.js:10
const API_HOST = 'http://127.0.0.1:9527'
// src/components/config/api.js:2
const HOST = 'http://127.0.0.1:9527'
```

Axios 实例虽支持 `VITE_API_BASE_URL` 环境变量，但回退到硬编码值。生产部署必然出问题。

### 5.3 [高] VideoStitching.vue 绕过 Store 和 API 模块

`VideoStitching.vue`（1,353 行）是独立单体组件：
- 导入旧 `API` 对象直接调 `fetch()`
- 自行维护项目状态（不使用 Pinia store）
- 重复实现 AudioPanel、MaterialsPanel、ClipPlanPanel 的全部逻辑

### 5.4 [中] snake_case / camelCase 处理不一致

后端已自动转 camelCase，但多处组件同时尝试两种格式：

```javascript
// MaterialsPanel.vue:17
row.videoName || row.video_name
// AudioPanel.vue:19
v.audioName || v.audio_name
```

应统一信任后端的 camelCase 转换。

### 5.5 [中] process.env 在 Vite 项目中不可用

```javascript
// src/utils/performance.js:4, errorHandler.js:93, logger.js:4
this.isEnabled = process.env.NODE_ENV !== 'production'
```

Vite 不提供 `process.env`，应使用 `import.meta.env.PROD`。

---

## 六、后端架构问题

### 6.1 [高] LLM 错误返回字符串而非异常

```python
# src/application/services/llm_adapter.py:54-56
except Exception as e:
    return f"错误: {str(e)}"  # 返回错误字符串
```

下游 ReAct Agent 会将 `"错误: connection refused"` 当作正常 LLM 输出，尝试正则提取 tool_call。同步和异步版本都有此问题。

### 6.2 [高] 服务层全同步，async 端点被迫阻塞

`VideoService`、`AudioService`、`CreativeService`、`RenderService` 全部是同步类。FFmpeg 操作 (`subprocess.run`) 可能耗时数分钟。在 async 端点中调用会阻塞整个事件循环。

### 6.3 [中] 双重 commit

```python
# src/infrastructure/db/session.py:31-32
yield db
db.commit()  # get_db 自动提交

# src/interfaces/api/project_api.py:112-113
db.commit()  # 端点又手动提交
```

`get_db` 退出时自动 commit，但多个端点还手动 commit。可能导致部分状态意外持久化。

### 6.4 [中] 双 Agent 系统冗余

- `react_agent.py`（ReActAgent）— 当前活跃
- `video_agent.py`（VideoDialogAgent）— 旧状态机

`agent_api.py` 只用 `get_react_agent()`。`intent_recognizer.py`（450+ 行）和 `slot_filler.py` 已成死代码。

### 6.5 [低] 旧工具页面组件未迁移 API 调用

`VideoStitching.vue`、`AIClip.vue`、`TTS.vue`、`VL.vue` 等旧组件仍用 `src/components/config/api.js` 旧 URL 常量，未迁移到 `src/api/modules/`。

---

## 七、代码质量

### 7.1 跨文件重复代码

| 重复内容 | 出现位置 |
|----------|----------|
| `formatTime()`、`statusText()` 等工具函数 | `UnifiedEditor.vue`、`VideoStitching.vue`、`AIClip.vue`、`ProjectList.vue` |
| `formatMessage()`（`\n` → `<br>`） | `ChatSidebar.vue:80`、`AIClip.vue:542`、`LLMChat.vue:171` |
| `getClipWidth()`、`parseSeconds()` | `ClipPlanPanel.vue`、`PreviewPanel.vue` |
| 视频上传逻辑（80% 相同） | `video_service.py:39 upload_video_file()` 与 `:119 upload_video_file_from_bytes()` |
| VL payload 构造 | `core_nexus_client.py` 中 4 处完全相同的 VL payload 代码 |
| Ripple 效果 | `useRipple.js`（composable，从未被导入）、`ripple.js`（指令）、`ripple.css` 三份实现 |

### 7.2 死代码 / 未使用文件

| 文件 | 说明 |
|------|------|
| `src/composables/useRipple.js` | 从未被导入 |
| `src/composables/useTheme.js` | 从未被导入 |
| `src/components/editor/ProjectHeader.vue` | 从未被引用 |
| `src/api/index.js` | 只导出 `systemApi`，其他模块缺失 |
| `src/components/config/fluxJson.js` | 1,428 行静态 JSON 配置，打入主 bundle |

### 7.3 代码异味

| 问题 | 位置 |
|------|------|
| `__import__('time').time()` 替代正常 import | `exception_handlers.py:49`、`session_manager.py:219`、`tool_registry.py:780` |
| `import json` 在函数内部重复导入 | `core_nexus_client.py:140,226,415,468` |
| 裸 `except:` 吞掉所有异常 | `exception_handlers.py:109`、`video_agent.py:553` |
| 变量名 `config` 遮蔽模块级 import | `ffmpeg_adapter.py:225` |
| `ffmpeg_adapter.py` `__main__` 块含硬编码 Windows 路径 | `:951-963` |

### 7.4 错误被静默吞掉

```javascript
// 前端：多处 .catch(() => {})
// VideoStitching.vue:1314, AIClip.vue:346

// Pinia store：仅 console.error，无用户提示
// project.js saveField(), saveFields(), refreshMaterials(), refreshBgmList()
```

---

## 八、UI / UX 问题

### 8.1 AI 回复不渲染 Markdown

`ChatSidebar.vue`、`AIClip.vue`、`LLMChat.vue` 中 AI 回复只做 `\n` → `<br>` 转换。代码块、列表、加粗等 Markdown 语法显示为原始文本。

### 8.2 破坏性操作无确认

| 操作 | 组件 |
|------|------|
| 重新生成剪辑方案（直接清空） | `ClipPlanPanel.vue:118` |
| 清除所有输出视频（无确认弹窗） | `PreviewPanel.vue:116` |

### 8.3 缺少加载状态

- `ChatSidebar.vue` 清空聊天无 loading 指示
- `ClipPlanPanel.vue` 重新生成直接置空 planData，无确认和 loading

### 8.4 编辑器布局无响应式

```css
/* src/components/editor/UnifiedEditor.vue:299 */
grid-template-columns: 4fr 3fr 2fr;
```

三栏布局无 media query，屏幕 < 900px 时面板压缩至不可用。

### 8.5 主题不兼容

多处硬编码颜色（`#409eff`、`#333`、`#f5f7fa`），假设深/浅色主题。切换主题时显示异常。

### 8.6 无障碍访问缺失

- 图标按钮无 `aria-label`
- `<span>` 交互元素无 `tabindex` / `role="button"` / `@keydown.enter`
- 聊天输入框 Enter 发送，无 Shift+Enter 换行支持

---

## 九、数据库问题

### 9.1 缺少索引

高频查询列无索引：

| 表 | 缺失索引列 |
|----|-----------|
| `VideoSource` | `del_flag`, `video_type`, `video_name` |
| `VideoProject` | `status` |
| `AudioSource` | `del_flag` |

### 9.2 缺少外键约束

```python
# video_project.py
speaker_id  → AudioSource.id    # 无 ForeignKey
bgm_id      → BGMItem.id        # 无 ForeignKey
ClipPlanItem.project_id → VideoProject.id  # 无 ForeignKey
```

可产生孤立引用数据。

### 9.3 时间字段不一致

| 实体 | 列类型 | 默认值 |
|------|--------|--------|
| VideoSource / AudioSource | `TIMESTAMP` | `func.current_timestamp()` |
| VideoProject / BGMItem | `DateTime` | `datetime.utcnow` |
| DialogSession | `DateTime` | `datetime.utcnow` |

应统一为一种模式。

### 9.4 SQLite 并发限制

```python
# src/infrastructure/db/session.py:16
connect_args={"check_same_thread": False}
```

SQLite 写并发极弱，多用户同时操作会频繁出现 `database is locked` 错误。

---

## 十、优先级汇总

### P0 — 必须立即修复（功能不可用或安全漏洞）

| # | 问题 | 类型 | 位置 |
|---|------|------|------|
| 1 | AudioService 缺少 db 参数 | 运行时崩溃 | `project_api.py:284`, `render_service.py:189` |
| 2 | SoVits V4 导入路径错误 | 运行时崩溃 | `audio_service.py:301` |
| 3 | LLMChat SSE 端点不存在 | 功能不可用 | `LLMChat.vue:97` |
| 4 | v-html XSS 注入（4 处） | 安全漏洞 | `ChatSidebar.vue`, `AIClip.vue`, `LLMChat.vue`, `VL.vue` |
| 5 | Agent 工具路径穿越 | 安全漏洞 | `tool_registry.py:1143,1199` |
| 6 | 文件上传无类型校验 | 安全漏洞 | `video_api.py:55`, `tool_api.py:22` |

### P1 — 应尽快修复（影响用户体验或稳定性）

| # | 问题 | 类型 | 位置 |
|---|------|------|------|
| 7 | 双 API 请求系统不连通 | 架构 | `api/request.js` vs `utils/request.js` |
| 8 | API_HOST 硬编码 × 2 | 架构 | `utils/request.js:10`, `config/api.js:2` |
| 9 | 同步阻塞 async 端点 | 性能 | `core_nexus_api.py` 多处 |
| 10 | LLM 错误返回字符串 | 稳定性 | `llm_adapter.py:54-56` |
| 11 | ffmpeg 失败返回 None | 稳定性 | `ffmpeg_adapter.py:940` |
| 12 | VideoStitching.vue 1353 行单体 | 维护性 | `VideoStitching.vue` |
| 13 | `process.env` 在 Vite 中不可用 | 兼容性 | `performance.js`, `errorHandler.js`, `logger.js` |
| 14 | fetch 调用未检查 response.ok | 稳定性 | `store/project.js:192-274` |
| 15 | TTS.vue 相对路径仅同源可用 | 功能缺陷 | `TTS.vue:137` |

### P2 — 计划优化（提升代码质量和性能）

| # | 问题 | 类型 |
|---|------|------|
| 16 | N+1 查询 | 性能 |
| 17 | render_service 全表模糊扫描 | 性能 |
| 18 | refreshMaterials 串行请求 | 性能 |
| 19 | 缺少数据库索引 | 性能 |
| 20 | 缺少外键约束 | 数据完整性 |
| 21 | 时间字段类型不一致 | 一致性 |
| 22 | Element Plus 全量引入 | 包体积 |
| 23 | fluxJson.js 1428 行入主 bundle | 包体积 |
| 24 | 跨文件重复工具函数 | 可维护性 |
| 25 | 死代码 / 未使用文件 | 整洁度 |
| 26 | 双 Agent 系统冗余 | 整洁度 |
| 27 | AI 回复不渲染 Markdown | UX |
| 28 | 编辑器布局无响应式 | UX |
| 29 | Pinia store 过大（454 行） | 可维护性 |
