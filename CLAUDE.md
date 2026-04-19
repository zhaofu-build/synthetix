# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 视频剪辑平台，采用 **Tauri 2.0 桌面应用**架构。前端 Vue 3 嵌入 Tauri 窗口，后端 FastAPI 作为本地 API 服务（端口 9527）+ sidecar 打包。UI 采用**统一编辑器**：左侧工作区（剪辑方案/音频）+ 中间 AI 对话栏 + 右侧（素材库 + 视频预览），左右可折叠。顶部菜单栏提供文件操作、项目名称编辑和工具弹窗。

后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、VL 等 AI 服务。

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
│   ├── skill_loader.py           # Markdown 技能加载器（扫描 src/skills/ 目录的 .md 文件）
│   ├── project_memory.py         # 项目级用户偏好记忆
│   ├── knowledge_base.py         # BM25 知识库（轻量 RAG）
│   ├── multi_agent.py            # 多 Agent 协作（Planner→Executor→Reviewer）
│   └── prompts.py                # LLM 提示词模板
│
├── extensions/                   # 扩展/插件目录
│   └── subtitle_style/           # 示例：字幕风格预设扩展
│
├── skills/                       # Markdown 技能定义目录
│
├── scripts/                      # 工具脚本（migrate_imports, update_imports）
│
├── domain/entities/              # SQLAlchemy 实体
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

config/                           # 分层配置（default.json + settings.json）
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
- `src/api/request.js`（axios）：API 模块使用，拦截器自动提取 `data.data`，业务错误弹 ElMessage
- `src/utils/request.js`（fetch）：导出 `assetUrl`、`API_HOST`，部分组件直接使用

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
3. 技能描述（`skill_loader.py` 加载的 Markdown 技能）
4. 扩展提示词（`extension_loader.py` 加载的扩展声明）
5. MCP 外部工具描述（`mcp_client.py` 发现的远程工具）

**三种处理模式**：
- `process_message()` — 同步返回完整结果
- `process_message_stream()` — SSE 流式，逐步 yield 事件（session/thinking/tool_start/tool_result/reply/done/error）
- `process_deep_research()` — 多阶段（分析素材→规划方案→执行操作），每阶段独立 TAOR 循环

关键实现细节：
- `build_system_prompt()` 使用字符串拼接（非 `.format()`），避免 `}` 冲突
- `END_CALL = "<" + "/tool_call>"` 避免被当作 XML 或 format 占位符
- `_strip_tool_call_hints()` 同时移除 `<think/thinking>` 深度思考块
- 最大 5 轮循环，防止无限循环
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
共 73 个工具，按类别：

- **基础视频操作**: cut_video, merge_videos, add_subtitle, change_speed, compress_video, split_video, convert_to_gif, convert_format
- **音频处理**: add_audio, extract_audio, mix_audio_to_video, separate_vocal, normalize_audio, equalize_audio, fade_audio, add_echo, denoise_audio, pitch_shift, reverse_audio
- **AI 能力**: smart_clip, analyze_video, analyze_video_vl, transcribe_video, generate_tts, generate_music, translate_text, detect_language
- **素材管理**: list_videos, get_video_description, search_material, search_files, download_video, delete_material, random_video, set_cover, update_description, list_audios
- **FFmpeg 滤镜**: adjust_brightness, blur_video, sharpen_video, rotate_video, flip_video, crop_video, fade_video, picture_in_picture, add_watermark, add_text_overlay, reverse_video, stabilize_video, scene_detect, slow_motion, color_adjust
- **系统工具**: get_current_time, list_directory, get_system_info, open_folder, task_status, time_convert, srt_to_ass, suggest_music, optimize_prompt, help, extract_frames, get_video_detail, batch_compress
- **多 Agent**: plan_clip, review_result
- **知识库**: knowledge_search, knowledge_add
- **浏览器自动化**: browser_navigate, browser_screenshot, browser_get_content, browser_get_links, browser_execute_js

### 工具注册关键约定
- `cut_video` 执行后会将结果注册为新素材入库（返回新 `video_id`），支持工具链式调用（剪切 → 分析）
- `list_videos` 支持 `project_id` 参数，按项目筛选素材
- `get_video_description` 无描述时提示用户使用 AI 分析
- `analyze_video_vl` 从数据库读取 `video.duration` 传给 VL，约束片段时间戳不超出视频实际时长

### 扩展/插件系统
- 扩展放在 `src/extensions/` 目录，每个扩展一个子目录，包含 `manifest.json` 和 Python 模块
- `manifest.json` 声明名称、版本、入口模块（如 `extensions.subtitle_style.main`）、系统提示词
- 入口模块可定义 `register_tools()` 函数注册自定义工具到 tool_registry
- `extension_loader.py` 自动将 `src/` 加入 `sys.path` 以支持模块导入
- 应用启动时自动加载（`lifespan()`），API 支持热重载

### MCP 协议
- `mcp_client.py` 管理外部 MCP Server 连接，通过 HTTP 发现和调用工具
- 工具名格式：`server_name.tool_name`
- 通过 `/api/mcp` API 动态注册/移除 Server

### 多 Agent 协作
- `multi_agent.py` 提供 Planner → Executor → Reviewer 子 Agent 流水线
- 子 Agent 复用 `tool_registry`，使用角色特定的系统提示词
- `plan_clip` 和 `review_result` 工具可在主 Agent 的 TAOR 循环中触发子流程

## Core-Nexus-AI 集成

所有 AI 推理通过 `CoreNexusClient` 调用（`src/shared/utils/core_nexus_client.py`）：

| 功能 | 同步方法 | 异步方法 |
|------|---------|---------|
| LLM 生成 | `llm_generate()` | `llm_generate_async()` |
| LLM 流式 | `llm_generate_stream()` | `llm_generate_stream_async()` |
| TTS 合成 | `tts_generate()` | `tts_generate_async()` |
| ASR 识别 | `asr_transcribe()` | `asr_transcribe_async()` |
| VL 理解 | `vl_generate()` | `vl_generate_async()` |
| 音乐生成 | `text_to_music()` | `text_to_music_async()` |

- `llm_adapter.py` 的 `generate_response_async()` 直接调用 `llm_generate_async()`（真异步，非 `asyncio.to_thread`）
- `select_model()` 根据消息长度 + 工具调用检测 + 迭代轮次选择快/慢模型
- 重试逻辑使用指数退避，同步用 `time.sleep()`，异步用 `await asyncio.sleep()`

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
```

### 分层配置
`config/default.json` 提供默认值，`config/settings.json` 覆盖（gitignored）。通过 `config_manager.py` 管理，支持 API 热重载。

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
- **安全**: Pydantic `validate_params` 失败抛异常（不静默返回）；LLM 修正后的参数会重新校验；FFmpeg 字符串参数经 `sanitize_ffmpeg_string()` 清洗
- **健康检查**: `GET /health` 检查数据库、ffmpeg、core-nexus 连接、活跃会话数
- **WebSocket**: 三个通道 `/ws`（Agent 对话）、`/ws/render`（渲染进度）、`/ws/system`（系统通知）
- **国际化**: `vue-i18n@9`，locale 文件在 `synthetix-vue/src/locales/`，设置页可切换语言
