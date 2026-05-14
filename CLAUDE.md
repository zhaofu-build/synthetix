# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 视频剪辑平台，采用 **Tauri 2.0 桌面应用**架构。前端 Vue 3 嵌入 Tauri 窗口，后端 FastAPI 作为本地 API 服务（端口 9527）+ sidecar 打包。UI 采用**统一编辑器**：左侧工作区（剪辑方案/音频）+ 中间 AI 对话栏 + 右侧（素材库 + 视频预览），左右可折叠。顶部菜单栏提供文件操作、项目名称编辑和工具弹窗。

后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、多模态（Multimodal）等 AI 服务。

## 运行应用

```bash
# 桌面模式（一键启动后端 + Tauri 窗口）
python main.py

# 前端开发模式（可选，热更新，端口 9528，需同时运行后端）
cd synthetix-vue && npm run dev

# Tauri 生产构建
python build_backend.py    # PyInstaller 打包 Python 后端为 exe
npx tauri build            # 生成 .msi 和 .exe 安装包（需在项目根目录运行）
```

`python main.py` 启动流程：后台线程启动 uvicorn API → 前台运行 `npx tauri dev`（自动构建前端 + 打开桌面窗口）。若 npx 不可用则回退到纯 Web 模式。

- API 文档: http://127.0.0.1:9527/docs （Swagger UI）
- 前端开发模式: http://127.0.0.1:9528（需同时运行后端）

## 前端开发

```bash
cd synthetix-vue
npm run lint       # lint
npm run format     # 格式化
npm run build      # 构建到 dist/
```

## 数据库迁移

```bash
alembic revision --autogenerate -m "描述"   # 生成迁移文件
alembic upgrade head                         # 执行迁移
alembic current                              # 查看当前版本
```

添加新实体后，必须在 `alembic/env.py` 中导入才能被迁移识别。

## 测试

```bash
pytest tests/unit/ -v                           # 运行单元测试
pytest tests/unit/test_xxx.py -v                # 运行单个测试
pytest tests/unit/ --cov=src --cov-report=html  # 覆盖率报告
```

## 架构

```
src/
├── agent/                        # 对话式剪辑 Agent
│   ├── react_agent.py            # ReAct Agent（TAOR 循环 + SSE 流式 + 深度研究）
│   ├── tool_registry.py          # @registry.register() 注册工具（含 Pydantic 校验、Hook、权限）
│   ├── session_manager.py        # 会话管理（内存缓存 + DB 双写）
│   ├── mcp_client.py             # MCP 协议客户端（动态接入外部工具服务器）
│   ├── extension_loader.py       # 扩展/插件加载器（扫描 src/extensions/ 目录）
│   ├── project_memory.py         # 项目级用户偏好记忆
│   ├── knowledge_base.py         # BM25 知识库（轻量 RAG）
│   └── multi_agent.py            # 多 Agent 协作（Planner→Executor→Reviewer）
│
├── extensions/                   # 扩展/插件目录（每个子目录一个扩展，含 manifest.json）
│
├── scripts/                      # 工具脚本（migrate_imports, update_imports）
│
├── domain/entities/              # SQLAlchemy 实体（12 个：VideoSource, AudioSource, VideoProject, ClipPlanItem, BGMItem, DialogSession, ComicProject, ComicSeries, ProjectTempFile, VideoShot, ConfigStore）
├── application/services/         # 业务服务
├── interfaces/api/               # FastAPI 路由
├── shared/                       # 常量、模型、工具函数
└── infrastructure/               # 数据库会话、Alembic、Repository

synthetix-vue/                    # 前端 Vue 3 + Vite + Pinia + Element Plus
synthetix-tauri/                  # Tauri 2.0 桌面应用（Rust）
├── src/main.rs, lib.rs           # Rust 入口（sidecar 启动）
├── tauri.conf.json               # Tauri 配置（窗口、构建、sidecar）
├── capabilities/                 # 权限声明
├── icons/                        # 应用图标
└── binaries/                     # sidecar 放置目录（PyInstaller 输出）

config/                           # 分层配置（default.json + DB config_store 表）
```

## 核心约定

### 命名转换
后端 snake_case → `success_response(to_camel=True)` 自动转 camelCase → 前端使用 camelCase。
前端 `debounceSave` 发送 snake_case key（`material_ids`, `target_duration` 等），后端 Pydantic 模型匹配 snake_case。

### 路由顺序
FastAPI 静态路由必须在动态路由（`/{id}`）之前定义，否则 `"bgm"` 等会被当作 `project_id`。

### 项目中心化
统一编辑器基于项目：
- 进入页面显示欢迎视图 → 新建/选择项目 → 加载编辑器
- 顶部菜单栏"文件"菜单可新建、切换、保存、导出项目
- 从项目列表点"打开" → 路由到 `/editor?projectId=X`
- 项目名称唯一，创建/修改时校验重复
- 前端 `watch` 各字段变化 → `debounceSave` (300ms, 每字段独立 timer) → `projectApi.update`

### 前端请求层
- `API_HOST` 单一来源：`synthetix-vue/src/utils/request.js`（读 `VITE_API_BASE_URL` 环境变量或默认 `http://127.0.0.1:9527`）
- `src/api/request.js`（axios）：所有 API 模块使用，拦截器自动提取 `data.data`，`success: false` 自动 reject 并弹 ElMessage
- `src/api/modules/` 下的 API 模块统一导出，通过 `src/api/modules/index.js` 聚合
- **SSE/流式请求**（`/api/agent/chat/stream`、`/api/nexus/llm/stream`）必须用原始 `fetch` + `ReadableStream`，不能用 axios
- `src/utils/request.js`（fetch）：仅导出 `assetUrl`、`API_HOST`，供 SSE 流式和外部 URL 使用
- 新增 API 方法：在 `src/api/modules/` 对应模块中添加，自动获得 axios 拦截器处理（`data.data` 提取、错误处理）

## Tauri 桌面应用

### 开发模式
`python main.py` 一键启动：uvicorn 后台线程 + `npx tauri dev` 前台进程。

### Sidecar（Python 后端打包）
- `build_backend.py` 用 PyInstaller 将 `main.py` 打包为 `synthetix-tauri/binaries/backend-x86_64-pc-windows-msvc.exe`
- Tauri 启动时通过 `tauri_plugin_shell` 拉起 sidecar
- 开发阶段 sidecar 不可用时跳过，依赖后台线程的 uvicorn

### 关键文件
- `synthetix-tauri/tauri.conf.json` — `frontendDist: ../synthetix-vue/dist`，`beforeDevCommand` 自动构建前端
- `synthetix-tauri/src/lib.rs` — sidecar 启动逻辑，失败不阻塞
- `synthetix-tauri/capabilities/default.json` — shell/process 权限

### 前置依赖
- Rust (rustup) — `winget install Rustlang.Rustup`
- Node.js — 已有
- Cargo PATH — `main.py` 自动添加 `~/.cargo/bin`

## 对话式 Agent 架构

### ReAct Agent（`react_agent.py`）

采用 **"笨引擎 + 聪明模型"** 架构：运行时不含业务逻辑，所有智能决策由 LLM 完成。

**TAOR 循环**: Think → Act → Observe → Repeat
```
用户输入 → LLM 思考 → 调用工具（或直接回复） → 观察工具结果 → 继续思考 → ... → 最终回复
```

**工具调用格式**（LLM 输出，正则解析）：
```
<tool_call name="tool_name">
{"param": value}
</tool_call}
```

**系统提示词注入链**（`_build_messages()` 按顺序拼接）：
1. 基础系统提示词（角色 + 工具描述 + 规则）
2. 项目偏好记忆（`project_memory.py` 提取的历史偏好）
3. 扩展提示词（`extension_loader.py` 加载的扩展声明）
4. MCP 外部工具描述（`mcp_client.py` 发现的远程工具）

**工具描述两模式策略**（`_build_messages()` 中根据 `active_extensions` 选择）：
- **@模板模式**：`get_tools_description_filtered(tool_names)` — 只注入扩展 pipeline 的 steps + `required_tools` 指定的工具（完整描述），其余省略
- **普通对话模式**：`get_tools_description_condensed(mode)` — 16 个 `CORE_TOOLS` 给完整参数描述，其余只给名称+简述

**动态工具补充**（TAOR 循环中）：普通对话模式下，当 LLM 调用了非核心工具时，自动追加 system 消息补充该工具的完整参数描述（`get_tool_full_description()`）。每个工具只补充一次，不修改 system prompt，保留 KV Cache。

**三种处理模式**：
- `process_message()` — 同步返回完整结果
- `process_message_stream()` — SSE 流式，逐步 yield 事件（session/thinking/tool_start/tool_result/reply/done/error）
- `process_deep_research()` — 多阶段（分析素材→规划方案→执行操作），每阶段独立 TAOR 循环

关键实现细节：
- `build_system_prompt()` 使用字符串拼接（非 `.format()`），避免 `}` 冲突
- `END_CALL = "<" + "/tool_call>"` 避免被当作 XML 或 format 占位符
- `_strip_tool_call_hints()` 同时移除 `<think/thinking>` 深度思考块
- 最大 10 轮循环，防止无限循环
- `project_id` 自动注入工具参数
- `last_video_list` 缓存视频列表供序数解析（"第一个" → index 0）
- `select_model()` 根据消息复杂度选择快/慢模型（第 0 轮 + 短文本 + 无工具调用 → 快模型）

**新增工具只需修改 `tool_registry.py`**：注册工具函数即可，LLM 自动从系统提示词中学习工具用法。

### 会话管理
`session_manager.py` 中 `DialogState` 维护每个会话状态，`SessionManager` 提供内存 + DB 双写持久化。`DialogState` 关键字段：`project_id`, `last_video_list`, `last_referenced_video_id`。

### 工具注册模式
```python
# src/agent/tool_registry.py

# 1. 定义 Pydantic 参数模型（带校验）
class CutVideoParams(BaseModel):
    video_id: int = Field(..., description="视频 ID")
    start_time: str = Field(default="00:00:00", description="开始时间 (HH:MM:SS)")
    end_time: Opt[str] = Field(default=None, description="结束时间 (HH:MM:SS)")

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time_format(cls, v):
        if v and not re.match(r'^\d{2}:\d{2}:\d{2}(\.\d+)?$', v):
            raise ValueError(f"时间格式错误: {v}")
        return v

# 2. 注册工具（支持 before_execute/after_execute Hook + 权限标注）
@registry.register(
    name="cut_video",
    description="剪切视频片段",
    parameters={"video_id": {...}, "start_time": {...}, "end_time": {...}},
    param_model=CutVideoParams,          # Pydantic 校验
    before_execute=validate_video_exists,  # 执行前 Hook
    permission="modify",                  # read_only / modify / destructive
)
async def tool_cut_video(video_id: int, start_time: str = "00:00:00",
                         end_time: str = None, **kwargs) -> Dict[str, Any]:
    ...
```

Hook 机制：`before_execute` 接收 params dict，可校验/修改后返回；`after_execute` 接收 result dict。`react_agent.py` 的 `_execute_tool()` 在执行前后调用。

**工具权限**：`read_only`（自动执行）→ `modify`（需确认）→ `destructive`（必须确认）。SSE 流式推送中 `tool_start` 事件包含 `permission` 字段。

### 已注册工具分类
共 106+ 个工具（3 个 category: common 32, video 82, comic 10），按类别：

- **基础视频操作**: cut_video, merge_videos, image_to_video, add_subtitle, change_speed, compress_video, split_video, convert_to_gif, convert_format
- **音频处理**: add_audio, extract_audio, mix_audio_to_video, separate_vocal, normalize_audio, equalize_audio, fade_audio, add_echo, denoise_audio, pitch_shift, reverse_audio
- **AI 能力**: smart_clip, analyze_video, analyze_video_vl, transcribe_video, generate_tts, generate_music, translate_text, detect_language
- **素材管理**: list_videos, get_video_description, search_material, search_files, download_video, delete_material, random_video, set_cover, update_description, list_audios
- **字幕样式**: subtitle_style_preset（扩展）
- **FFmpeg 滤镜**: adjust_brightness, blur_video, sharpen_video, rotate_video, flip_video, crop_video, fade_video, picture_in_picture, add_watermark, add_text_overlay, reverse_video, stabilize_video, scene_detect, slow_motion, color_adjust
- **系统工具**: get_current_time, list_directory, get_system_info, open_folder, task_status, time_convert, srt_to_ass, suggest_music, optimize_prompt, help, extract_frames, get_video_detail, batch_compress
- **多 Agent**: plan_clip, review_result
- **知识库**: knowledge_search, knowledge_add
- **浏览器自动化**: browser_navigate, browser_screenshot, browser_get_content, browser_get_links, browser_execute_js

### 工具注册关键约定
- `cut_video` 执行后会将结果注册为新素材入库（返回新 `video_id`），支持工具链式调用（剪切 → 分析）
- `list_videos` 支持 `project_id` 参数，按项目筛选素材（含正式素材 + 临时素材）
- `get_video_description` 无描述时提示用户使用 AI 分析
- `analyze_video_vl` 从数据库读取 `video.duration` 传给 VL，约束片段时间戳不超出视频实际时长
- `run_ffmpeg_cmd(cmd)` **已自动加 `ffmpeg` 前缀**，调用时不应再传 `'ffmpeg'`。三个变体：`run_ffmpeg_cmd`（同步）、`run_ffmpeg_cmd_async`（线程池）、`run_ffmpeg_cmd_atomic`（原子写入：先写临时文件再 rename）

### 扩展/插件系统
- 扩展放在 `src/extensions/` 目录，每个扩展一个子目录，包含 `manifest.json` 和 Python 模块
- `manifest.json` 声明名称、版本、入口模块（如 `extensions.subtitle_style.main`）、系统提示词
- 入口模块可定义 `register_tools()` 函数注册自定义工具到 tool_registry
- `extension_loader.py` 自动将 `src/` 加入 `sys.path` 以支持模块导入
- 应用启动时自动加载（`lifespan()`），API 支持热重载
- 技能（原 `src/skills/` 的 .md 文件）已迁移为扩展，统一由 `extension_loader.py` 管理

**扩展分级**：
- `level: "system"` — 常驻注入，不可编辑/禁用/删除（如 `auto_execute_rules`）
- `level: "user"` — 按需注入，可通过 UI 编辑/禁用/删除

**扩展模式**：`mode` 字段（`video` / `comic` / `all`）控制扩展在哪种编辑模式下激活。`get_extensions_prompt_section()` 按 mode 过滤。

**流水线模板**：扩展可在 `manifest.json` 的 `pipeline` 字段定义流水线：
- `user_params`：用户填写的参数（支持 text/number/select 类型，`{{param}}` 引用语法）
- `steps`：工具执行步骤（`$stepN.field` 引用前序步骤结果）
- `required_tools`：声明额外需要的工具（不在 steps 中但 system_prompt 引用的），`get_extension_tools()` 自动合并 steps + required_tools
- `PipelineEngine` 解析模板 → `PlanExecutor` 执行（SSE 流式推送 `plan_step_start/result` 事件）
- 前端 `PipelineGallery.vue` 提供模板浏览/参数填写/工具选择/执行 UI
- 聊天输入框 `@pipeline_name` 触发直接执行（通过 `active_extensions` context）

### MCP 协议
- `mcp_client.py` 管理外部 MCP Server 连接，通过 HTTP 发现和调用工具
- 工具名格式：`server_name.tool_name`
- 通过 `/api/mcp` API 动态注册/移除 Server

### 多 Agent 协作
- `multi_agent.py` 提供 Planner → Executor → Reviewer 子 Agent 流水线
- 子 Agent 复用 `tool_registry`，使用角色特定的系统提示词
- `plan_clip` 和 `review_result` 工具可在主 Agent 的 TAOR 循环中触发子流程

### 工具拦截器链
全局拦截器（`src/agent/interceptors.py`）在每次工具调用前后执行，独立于单个工具的 `before_execute/after_execute` hook：
- **Pre-interceptors**：`param_injection_interceptor`（时间戳自动转 HH:MM:SS）、`cache_interceptor`（只读查询缓存）
- **Post-interceptors**：`material_registration_interceptor`（自动注册视频产出为素材）、`auto_index_interceptor`（触发 VideoIndexer 后台索引）、`execution_log_interceptor`（日志记录）
- 通过 `register_default_interceptors(registry)` 在 `main.py` lifespan 中注册

### 计划执行引擎
除了 TAOR 循环，还有一套**结构化计划执行**模式：
- `plan_generator.py`：单次 LLM 调用生成 JSON 计划（有序步骤，含 risk 标注）
- `plan_executor.py`：顺序执行步骤，解析 `$stepN.field` 引用，SSE 推送进度。destructive 步骤需用户确认
- `pipeline_engine.py`：将扩展的 pipeline 模板解析为计划步骤，处理 `{{param}}` 参数替换

## Core-Nexus-AI 集成

所有 AI 推理通过 `CoreNexusClient` 调用（`src/shared/utils/core_nexus_client.py`）：

| 功能 | 同步方法 | 异步方法 |
|------|---------|---------|
| LLM 生成 | `llm_generate()` | `llm_generate_async()` |
| LLM 流式 | `llm_generate_stream()` | `llm_generate_stream_async()` |
| TTS 合成 | `tts_generate()` | `tts_generate_async()` |
| ASR 识别 | `asr_transcribe()` | `asr_transcribe_async()` |
| 多模态 (原 VL) | `multimodal_generate()` | `multimodal_generate_async()` |
| 音乐生成 | `text_to_music()` | `text_to_music_async()` |
| 视频生成 (统一) | `video_gen()` | `video_gen_async()` |

> **接口变更说明**：原 VL 接口（`/vl`）已合并为多模态接口（`/multimodal`），原 `text_to_video` + `image_to_video` 已合并为统一视频生成接口（`/video-gen`）。旧方法名作为别名保留（`vl_generate = multimodal_generate`，`text_to_video = video_gen`）。

- `llm_adapter.py` 的 `generate_response_async()` 直接调用 `llm_generate_async()`（真异步，非 `asyncio.to_thread`）
- `select_model()` 根据消息长度 + 工具调用检测 + 迭代轮次选择快/慢模型
- 重试逻辑使用指数退避，同步用 `time.sleep()`，异步用 `await asyncio.sleep()`

### API Key 配置流程

core-nexus-ai 认证使用 `X-API-Key` header（格式 `cn-xxx`）。

**配置来源优先级**：设置页 UI → DB `config_store` 表 → `.env` 文件

数据流：
```
设置页 "AI 服务" tab → PATCH /api/tools/config {"core_nexus.api_key": "cn-xxx"}
  → cfg_set() 持久化到 DB config_store
  → config.llm_key = api_key（注意：config.py 变量名是小写 llm_key）
  → reset_client() → CoreNexusClient._init_key_pool() 从 config.llm_key 读取
```

**关键注意**：
- `config.py` 中 API Key 变量名是小写 `llm_key`（非 `LLM_KEY`）。`_init_key_pool` 优先读 `config.llm_key`，兼容 `config.LLM_KEY`。
- `_init_key_pool` 支持逗号分隔多 key 轮换，单个 key 也正常工作。
- `core_nexus_api.py` 中 `list_models` 和 `test_connection` 使用裸 httpx 调用（非 CoreNexusClient），需手动注入 `X-API-Key` header。
- 设置页 core_nexus API Key 同步时，也设置 `TTS_KEY`、`ASR_KEY`、`MULTIMODAL_KEY`（作为 fallback，各自独立配置时优先用独立 key）。

### KV Cache（Prompt Caching）

ReAct Agent 的 TAOR 循环启用了 KV Cache，每轮迭代自动复用已计算的 token 前缀：

```python
# react_agent.py 中的 TAOR 循环
provider_options = {"use_kv_cache": True}
if kv_session_id:
    provider_options["session_id"] = kv_session_id
response_text = await generate_response_async(messages, provider_options=provider_options)
# 从响应提取 session_id 供下一轮复用
kv_session_id = client.last_response.get("output", {}).get("session_id")
```

`CoreNexusClient` 的 4 个 LLM 方法均支持 `provider_options` 参数，`llm_adapter` 的 4 个 `generate_response*` 函数透传该参数。`client.last_response` 属性存储最近一次 LLM 调用的完整响应（含 `session_id`、`cached_tokens`）。

## 配置

### 环境变量 (.env)
```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=*
API_PORT=9527
FAST_MODEL=              # 快速模型名（可选，不配则统一用主模型）
SLOW_MODEL=              # 主模型名（可选）
FAST_MODEL_THRESHOLD=100 # 快模型使用的消息长度阈值
CHROME_CDP_URL=          # CDP 浏览器地址（可选，默认 http://127.0.0.1:9222）
TIAN_API_KEY=            # 天行数据新闻 API Key（可选）
NEWS_API_KEY=            # NewsAPI.org 国际新闻 Key（可选）
VIDEO_API_KEYS=          # Pexels 视频 API Key
PIXABAY_API_KEY=         # Pixabay 图片/视频 API Key
```

### 分层配置
配置已从文件迁移到 **DB `config_store` 表**：
- 代码内默认值（`config_manager.py` 的 `_DEFAULTS` dict）→ DB `config_store` 表覆盖 → 环境变量 fallback
- `config_manager.py` 中 `_migrate_from_settings_json()` 执行一次性迁移：读 `settings.json` → 写 DB → 重命名为 `.json.bak`
- `ConfigStore` 实体（`domain/entities/config_store.py`）存储 key-value，key 为点分路径（如 `core_nexus.api_key`）
- `ConfigStoreRepository` 提供 `upsert()` 和 `get_all_as_dict()`
- 支持通过 API 热重载，线程锁保护读写，内置 9 条参数校验规则（类型 + 范围）

## Docker 部署

```bash
docker-compose up --build
# 挂载卷：./src/db（数据库）、./static（素材文件）
# 端口：9527:9527
```

## 其他约定

- **数据库**: SQLite (`src/db/synthetix.db`)，Alembic `render_as_batch=True` 兼容 SQLite ALTER TABLE
- **FFmpeg**: 二进制文件在 `ffmpeg/` 目录，所有视频处理通过 `subprocess.run(['ffmpeg', ...])` 本地执行，零网络依赖。`run_ffmpeg_cmd()` 抛出 `RuntimeError`（非 `CalledProcessError`）
- **静态文件**: 后端通过 `main.py` 的全捕获路由提供 `/static/` 文件和前端 SPA，前端通过 `assetUrl(path)` 构建完整 URL
- **SPA 挂载**: `main.py` 将 `synthetix-vue/dist` 挂载到 FastAPI：`/` 和 `/{path:path}` 路由依次检查后端静态文件、前端构建产物，未命中则回退 `index.html`（Vue Router 客户端路由）
- **VL 视频分析**: `qwen_vl_adapter.py` 中本地文件通过 `_file_to_data_url()` 转 base64 data URL 再发给 core-nexus-ai，不能直接传文件路径。`video_summary()` 接受 `duration` 参数，在 prompt 中约束片段时间戳不超过视频实际时长
- **项目输出视频**: `VideoProject.output_videos` (JSON 数组) 存储渲染输出列表 `[{path, created_at}]`，支持多个输出
- **el-tag type**: 合法值为 `success/warning/danger/info/primary`，不能传空字符串 `''`
- **ErrorBoundary**: `MainLayout.vue` 用 `ErrorBoundary.vue` 包裹 `router-view`
- **工具页面**: TTS/ASR/VL 等工具页通过 `defineAsyncComponent` 懒加载，以 `el-dialog` 弹窗形式打开，不使用独立路由
- **安全**: Pydantic `validate_params` 失败抛异常（不静默返回）；LLM 修正后的参数会重新校验；FFmpeg 字符串参数经 `sanitize_ffmpeg_string()` 清洗；`RateLimitMiddleware`（`src/shared/middleware/rate_limit.py`）按路由前缀限流（Agent 20/min、Core-Nexus 10/min、TTS 10/min、默认 60/min）
- **健康检查**: `GET /health` 检查数据库、ffmpeg、core-nexus 连接、活跃会话数、系统资源
- **资源监控**: `resource_monitor.py` 在启动时检测 CPU/RAM/GPU/磁盘，自动降级 FFmpeg 参数（<4GB RAM: 1 并行+GPU 关闭+CRF 28；≥16GB: 4 并行）。`get_resource_profile()` 全局单例
- **AI 调用指标**: `observability.py` 记录每次 AI 调用到 `~/.synthetix/metrics/ai_calls.jsonl`（10MB/文件，5 备份），`GET /api/metrics/ai?hours=24` 返回聚合统计
- **结果缓存**: `result_cache.py` 基于文件 hash 的 JSON 缓存（`~/.synthetix/cache/`，默认 24h TTL），`@cached_result(prefix, ttl, key_args)` 装饰器用于 ASR/VL/ffprobe 结果
- **异常体系**: `src/shared/exceptions/` — `BaseAppException` 基类 + 15 个子类（ValidationException、VideoProcessingException、ExternalServiceException 等），全局异常处理器注册到 FastAPI，统一返回 `{success: false, message, code, error}` JSON
- **视频索引**: `VideoShot` 实体 + `VideoIndexer` 服务 — 场景检测、关键帧提取、逐镜头 VL 分析，由 `auto_index_interceptor` 在新素材注册时自动触发
- **WebSocket**: 三个通道 `/ws`（Agent 对话）、`/ws/render`（渲染进度）、`/ws/system`（系统通知）
- **国际化**: `vue-i18n@9`，locale 文件在 `synthetix-vue/src/locales/`，设置页可切换语言。核心 UI 组件已使用 `t('key')` 替代硬编码中文，新增 UI 文字时需同步添加到 `zh-CN.js` 和 `en-US.js`
- **路径安全**: `src/shared/utils/path_security.py` 提供 `validate_path_in_allowed_dir()`，API 端点接受文件路径参数时必须调用该校验（限制在 `ROOT_DIR` 和 `static/` 内）
- **文件上传限制**: 各 API 端点有大小/扩展名校验（图片 10MB、音频 50MB、项目导入 10MB、TTS 参考音频 20MB）

## 项目临时文件系统

聊天上传和工具产出（剪切/合并/下载/图片处理等）存入**项目专属临时目录**，不进入素材库。

### 目录结构
```
static/temp/{project_id}/           # 每个项目独立目录
  ├── upload_xxx.jpg                # 聊天上传的文件
  ├── cut_xxx_123.mp4               # 工具产出的文件
  └── ...
```

### 数据库表 `project_temp_file`
- 实体：`src/domain/entities/project_temp_file.py`
- Repository：`src/infrastructure/repositories/temp_file_repository.py`
- 字段：`project_id`（FK）、`session_id`、`file_name`、`file_path`、`web_path`、`file_type`、`file_size`、`source`（upload/cut/merge/download 等）

### 双记录策略
上传文件时同时创建两条记录：
1. **`ProjectTempFile`** — 用于级联删除（删项目/清会话时自动清理）
2. **`VideoSource`（`is_temp=True`）** — 用于工具通过 `video_id` 引用（图片处理、分析等工具需要 `video_id`）

### 级联删除
- 删除项目 → `TempFileRepository.delete_by_project()` + 删除 `static/temp/{project_id}/` 目录
- 删除/清空会话 → `TempFileRepository.delete_by_session()`
- 删除单个临时文件 → `DELETE /api/projects/temp-files/{id}`

### 工具产出保存
`tool_registry.py` 中的 `_save_temp_file(src_path, project_id, file_type, source)` helper：
- 将工具产出文件移到 `static/temp/{project_id}/`
- 创建 `ProjectTempFile` 记录
- 返回 `{ temp_file_id, web_path, local_path, output_type, is_temp_asset: True }`
- 被 `cut_video`、`merge_videos`、`download_video`、图片处理工具等调用
- 无 `project_id` 时回退到素材库（创建 `VideoSource` 记录）

### "存入库"操作
`POST /api/projects/temp-files/{id}/save-to-library`：将临时文件复制到 `static/source_videos/`，创建正式 `VideoSource` 记录。

### 前端适配
- 上传返回 `video_id` + `temp_file_id`，附件上下文注入 LLM 时包含素材 ID
- `TempAssetCard` 组件兼容 snake_case（SSE 直传）和 camelCase（API 重载后 `to_camel` 转换）
- `_saveChatHistory()` 使用 `JSON.parse(JSON.stringify(...))` 深拷贝确保 reactive proxy 正确序列化

## 常见陷阱

### validate_params 会丢弃 Pydantic 模型外的字段

`Tool.validate_params()` 使用 Pydantic model 校验参数。`react_agent.py` 自动注入 `project_id` 到 params，但大多数工具的 Pydantic 模型不含 `project_id`。当前 `validate_params()` 已做回填处理（保留额外字段），但新增工具时需注意：如果工具需要 `project_id`，确保它通过 `kwargs` 获取，**不要依赖 Pydantic 模型声明**（除非确实需要校验）。

### web_path 不是文件系统路径

工具返回的 `web_path`（如 `static/uploads/xxx.wav`、`/static/temp/7/tts_xxx.wav`）是 URL 路径，不能直接传给 FFmpeg。需要转为绝对路径：
```python
abs_path = os.path.join(str(config.ROOT_DIR_WIN), web_path.lstrip('/'))
```
`add_audio`、`mix_audio_to_video`、`image_to_video` 等接受文件路径的工具已内置此解析逻辑。

### get_db_context() 默认不提交

`get_db_context(commit=False)` 的 `commit` 参数默认为 `False`——退出 context manager 时**回滚**所有写操作。忘记传 `commit=True` 会导致写入静默丢失。FastAPI DI 的 `get_db()` 则默认自动提交。

### 临时文件必须用 _save_temp_file 保存

工具产出文件**不能**在外部 `get_db_context()` session 中直接 `repo.create()` 再返回 ID——该 session 默认 `commit=False`，退出时回滚，后续工具查不到。正确做法：
1. 有 `project_id` → 调用 `_save_temp_file()`（内部有独立 session + `db.commit()`）
2. 无 `project_id` → 使用独立的 `get_db_context()` 并手动 `db.commit()`

### 字幕系统 ASS 颜色格式

ASS 颜色格式为 `&HBBGGRR`（注意不是 RGB 而是 BGR），6 位十六进制。不要使用 8 位格式 `&H00FFFFFF`——前两位 alpha 为 `00` 表示全透明，字幕会不可见。正确写法：白色 `&Hffffff`，黑色 `&H000000`。

### 字幕临时文件路径

`ffmpeg_adapter.py` 中 `add_subtitle()` 的 SRT/ASS 临时文件已改为写入 `tempfile.gettempdir()`。不要改回相对路径——相对路径会写入 CWD（项目根目录），进程中断时残留。

### 字体文件集中管理

FFmpeg `drawtext` 滤镜在 Windows 上不能使用含盘符冒号的绝对路径。`_prepare_font_for_file()` 已改为从 `static/fonts/` 集中目录计算相对路径，不再复制字体到输入文件目录。

### 视频合并必须使用 concat demuxer

`ffmpeg_adapter.py` 中 `concatenate_videos_with_filter` 和 `concatenate_videos_with_transitions` **禁止使用 `-filter_complex concat`**，该方式同时打开所有输入视频并行解码，多视频合并时内存会爆炸。统一使用 **concat demuxer**（`-f concat -safe 0`）顺序读取，内存占用恒定。

流程：
1. `_can_stream_copy()` 检查所有视频编码/分辨率是否一致
2. 一致 → `_merge_with_concat_demuxer()` 用 `-c copy` 零重编码拼接
3. 不一致 → `_normalize_video_for_concat()` 逐个标准化（一次只开一个文件），再 concat demuxer
4. `concatenate_videos_with_transitions` 的中间文件已由 `cut_video_silence` 统一格式，直接 concat demuxer 后补静音轨

### 视频入库标准化

所有视频文件进入系统时自动标准化为 **h264 + aac + yuv420p**，确保后续合并操作可直接 stream copy。

`ffmpeg_adapter.py` 中 `standardize_video(input_path)` 函数：
- ffprobe 检查是否已是标准格式 → 已是则跳过（~10ms）
- 否则原子替换（临时文件 + `os.replace`），h264 fast preset CRF 23
- 失败时保留原文件，仅打 warning 日志
- 按 `file_type` 和扩展名自动跳过非视频文件（audio/image/document）
- 受 `config/default.json` 中 `ffmpeg.standardize_on_ingest` 开关控制（默认 true）

**注入点**（6 个，覆盖所有视频入库路径）：

| 文件 | 函数 | 覆盖场景 |
|------|------|---------|
| `tool_registry.py` `_save_temp_file` | Agent 下载 + 40+ 工具产出（`if file_type == "video"`） |
| `video_service.py` `upload_video_file` | 流式上传 |
| `video_service.py` `upload_video_file_from_bytes` | 字节上传 |
| `video_service.py` `download_video` | URL 下载 |
| `video_downloader_adapter.py` `download_video` | Pexels/Pixabay 下载 |
| `tool_api.py` `upload_file` | 聊天上传（`if file_type == "video"`） |

**注意**：新增视频入库路径时，必须在文件写入后、ffprobe/DB 操作前调用 `standardize_video(path)`。

### to_dict() 双系统（新增字段时必查）

项目中存在两套 `to_dict()` 机制：
- **ToDictMixin**（`domain/entities/mixins.py`）：自动遍历 `__table__.columns`，新增列自动包含
- **Repository/Entity 手动覆盖**：硬编码字段列表，新增列不会自动出现

手动覆盖的位置：
| 文件 | 行 | 类型 |
|------|-----|------|
| `video_repository.py` | 170 | Repository 覆盖 |
| `audio_repository.py` | 110 | Repository 覆盖 |
| `video_project.py` | 54 | Entity 覆盖 |
| `video_project.py` | 102 | ClipPlanItem Entity 覆盖 |
| `comic_project.py` | 40 | Entity 覆盖 |
| `bgm_item.py` | 24 | Entity 覆盖 |

**规则**：给任何实体新增列后，必须同时更新对应的 `to_dict()` 手动覆盖（如果存在），否则 API 响应中该字段会静默丢失。

### Alembic 自动生成的迁移需手动清理

`alembic revision --autogenerate` 在 SQLite batch 模式下可能生成无名的 FK 约束（`batch_op.create_foreign_key(None, ...)`），执行时会报 `ValueError: Constraint must have a name`。解决方法：检查生成的迁移文件，移除不需要的 FK/index 操作，只保留实际新增的列。

**SQLite batch mode 迁移注意事项**：
- `batch_alter_table` 通过重建表实现 ALTER TABLE，操作在 `__exit__` 时 flush 执行，`try/except` 无法捕获单个操作失败
- `drop_constraint` 会报 `No such constraint` — 如果旧约束名不存在。**不要用 `drop_constraint`**，直接 `create_foreign_key` 即可（重建表时会自动使用新 FK 定义）
- `create_index` 不检查 `IF NOT EXISTS`，重复执行会报 `index already exists`。对于可能重复运行的迁移，先用 `sqlite_master` 查询检查索引是否存在
- 之前失败的迁移会残留 `_alembic_tmp_*` 临时表，需在迁移开头清理：`DROP TABLE IF EXISTS "_alembic_tmp_xxx"`

### subprocess 编码（Windows）

`subprocess.run()` 在 Windows 上 `text=True` 默认使用系统编码（GBK/CP936），处理中文路径时会报 `UnicodeDecodeError`。所有 `subprocess.run/call` 应使用 `encoding='utf-8', errors='replace'`。`run_ffmpeg_cmd()` 已修复；`ffmpeg_adapter.py`、`quality_service.py`、`ffmpeg_util.py` 中仍有遗漏，新增 subprocess 调用时务必指定 `encoding='utf-8'`。

### Element Plus 图标导入

`@element-plus/icons-vue` 不包含 `Cookie` 图标。使用前需确认图标存在，可用 `Present`（礼物盒）等替代。导入不存在的图标会导致 `vite build` 失败（Rollup 报 `"X" is not exported`）。

### run_ffmpeg_cmd 不要重复传 'ffmpeg'

`run_ffmpeg_cmd(cmd)` 内部已自动加 `ffmpeg` 前缀（`command = ["ffmpeg"]` + `command.extend(cmd)`）。调用时只传参数部分：`run_ffmpeg_cmd(['-y', '-i', path, ...])`，不要传 `run_ffmpeg_cmd(['ffmpeg', '-y', ...])`。

### 聊天历史保存时 reactive proxy 序列化

`_saveChatHistory()` 必须用 `JSON.parse(JSON.stringify(...))` 深拷贝 `this.messages`，否则 Vue reactive proxy 对象经 axios 序列化可能丢失嵌套属性（如 `toolCalls[].mediaInfo`、`attachments`）。

### API Key 冷启动同步

`main.py` lifespan 中从 `settings.json` 读取 `core_nexus.api_key` 并同步到 `config.llm_key`（以及 `TTS_KEY`、`ASR_KEY`、`MULTIMODAL_KEY` fallback）。如果只通过设置页 UI 配置但不同步到运行时，重启后首次 LLM 调用会失败（key 为空）。

`video_downloader_adapter.py` 提供统一搜索入口：
- `search_videos(term, min_duration, source)` — `source` 为 `pexels`/`pixabay`/`all`
- 每个结果返回双 URL：`url`（下载用，高清）+ `preview_url`（预览用，SD）
- 搜索词自动作为 `tags` 保存到素材
- 前端通过 `GET /api/videos/search-online?query=xxx&source=all` 调用

**API Key 配置**：
- Pexels Key：环境变量 `VIDEO_API_KEYS` 或设置页"视频/剪辑"Pexels Key
- Pixabay Key：环境变量 `PIXABAY_API_KEY` 或设置页"视频/剪辑"Pixabay Key
- 设置页保存的 key 通过 `tool_api.py` 的 `update_config` 同步到 `config.py` 运行时变量；`main.py` lifespan 从 `config_manager` 读取同步到运行时
