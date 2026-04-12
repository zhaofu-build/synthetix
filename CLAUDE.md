# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 视频剪辑平台，采用**统一编辑器**架构：左侧工作区（剪辑方案/音频）+ 中间 AI 对话栏 + 右侧（素材库 + 视频预览）。左右两侧支持折叠。顶部菜单栏提供文件操作、项目名称编辑和工具弹窗。旧的两个独立页面（AIClip、VideoStitching）保留路由做向后兼容。

后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、VL 等 AI 服务。

## 运行应用

```bash
# 启动 API (端口 9527)
python main.py

# 启动前端 (端口 9528)
cd synthetix-vue && npm run dev

# 构建前端
cd synthetix-vue && npx vite build

# lint
cd synthetix-vue && npm run lint

# 格式化
cd synthetix-vue && npm run format
```

- API 文档: http://127.0.0.1:9527/docs
- Web 界面: http://127.0.0.1:9528

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
├── agent/                    # 对话式剪辑 Agent
│   ├── react_agent.py        # ReAct Agent（TAOR 循环：Think→Act→Observe→Repeat）
│   ├── video_agent.py        # 旧 Agent（状态机，保留兼容）
│   ├── tool_registry.py      # @registry.register() 注册工具（含 Pydantic 校验、Hook）
│   ├── intent_recognizer.py  # 意图识别（规则匹配 + LLM 兜底，旧 Agent 使用）
│   ├── slot_filler.py        # 槽位填充（正则提取 + LLM 兜底，旧 Agent 使用）
│   ├── session_manager.py    # 会话管理（内存缓存 + DB 双写）
│   └── prompts.py            # LLM 提示词模板
│
├── domain/entities/          # SQLAlchemy 实体
│   ├── video_source.py       # 视频素材
│   ├── audio_source.py       # 音频素材（音色）
│   ├── video_project.py      # 视频项目 + ClipPlanItem
│   ├── bgm_item.py           # BGM 素材
│   └── dialog_session.py     # 对话会话持久化
│
├── application/services/     # 业务服务
│   ├── video_service.py, audio_service.py   # 视频/音频处理
│   ├── clip_planner.py       # AI 剪辑方案规划
│   ├── render_service.py     # 视频渲染（FFmpeg）
│   ├── llm_adapter.py        # LLM 调用封装（同步 + 真异步）
│   ├── ffmpeg_adapter.py     # FFmpeg 命令封装（所有视频处理走 subprocess.run）
│   └── creative_service.py   # 创意内容生成
│
├── interfaces/api/           # FastAPI 路由
│   ├── agent_api.py          # /api/agent
│   ├── project_api.py        # /api/projects
│   ├── video_api.py          # /api/videos
│   ├── audio_api.py          # /api/audios
│   └── core_nexus_api.py     # /api/nexus (AI 服务代理)
│
├── shared/
│   ├── constants.py          # 集中常量（文件大小、分页、视频参数、Agent 配置等）
│   ├── models/response.py    # success_response(to_camel=True) 自动转换
│   ├── models/timeline.py    # Timeline/ClipPlan 数据结构
│   └── utils/
│       ├── core_nexus_client.py  # core-nexus-ai 统一客户端（同步 + async）
│       ├── string_util.py        # 通用工具（JSON 解析、语言检测、参数清洗）
│       └── file_util.py          # 文件操作工具
│
└── infrastructure/
    ├── db/                   # 数据库会话、Alembic
    └── repositories/         # Repository 数据访问层

synthetix-vue/                # 前端 Vue 3 + Vite + Pinia + Element Plus
├── src/api/
│   ├── request.js            # axios 实例（自动提取 data.data）
│   ├── utils/request.js      # fetch 封装（assetUrl, API_HOST）
│   └── modules/              # API 模块（video, audio, ai, project, system）
├── src/store/modules/
│   ├── system.js             # 主题、系统配置
│   └── project.js            # 项目 CRUD、防抖自动保存、素材/BGM/音色管理
├── src/layouts/MainLayout.vue  # 顶部菜单栏（文件/工具/设置 + 项目名称编辑），工具以 el-dialog 弹窗打开
├── src/components/editor/      # 统一编辑器模块
│   ├── UnifiedEditor.vue     # 主页面（三区域 Grid: 工作区 | AI对话 | 右侧栏，左右可折叠）
│   ├── ChatSidebar.vue       # AI 对话栏（中间位置）
│   ├── WorkspacePanel.vue    # 工作区（上方剪辑方案 2/3 + 下方音频 1/3，可向左折叠）
│   ├── MaterialsPanel.vue    # 素材库（项目素材 + 素材管理/编辑弹窗）
│   ├── PreviewPanel.vue      # 视频预览（支持多个输出视频）+ 渲染导出
└── src/components/config/api.js  # API 端点常量 + API_HOST
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

### 前端 API 调用
```javascript
// 推荐：使用 API 模块（axios）
import { projectApi, videoApi, assetUrl, API_HOST } from '@/api/modules'
const data = await projectApi.getFull(id)

// 部分老代码直接用 fetch
import { API_HOST } from '@/api/modules'
const response = await fetch(`${API_HOST}/api/agent/chat`, { ... })
```

### 前端请求层
- `src/api/request.js`（axios）：API 模块使用，拦截器自动提取 `data.data`，业务错误弹 ElMessage
- `src/utils/request.js`（fetch）：工具函数，导出 `assetUrl`、`API_HOST`，部分组件直接使用

## 对话式 Agent 架构

### ReAct Agent（主 Agent，`react_agent.py`）

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

关键实现细节：
- `build_system_prompt()` 使用字符串拼接（非 `.format()`），避免 `}` 冲突
- `END_CALL = "<" + "/tool_call>"` 避免被当作 XML 或 format 占位符
- `_strip_tool_call_hints()` 同时移除 `<think/thinking>` 深度思考块
- 最大 5 轮循环，防止无限循环
- `project_id` 自动注入工具参数
- `last_video_list` 缓存视频列表供序数解析（"第一个" → index 0）

**新增工具只需修改 `tool_registry.py`**：注册工具函数即可，LLM 自动从系统提示词中学习工具用法。

### 旧 Agent（`video_agent.py`，保留兼容）

旧的状态机流程仍保留：IDLE → COLLECTING → CONFIRMING → EXECUTING。`intent_recognizer.py` 和 `slot_filler.py` 仅被旧 Agent 使用。`agent_api.py` 的 chat 端点默认使用 ReAct Agent。

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

# 2. 注册工具（支持 before_execute/after_execute Hook）
@registry.register(
    name="cut_video",
    description="剪切视频片段",
    parameters={"video_id": {...}, "start_time": {...}, "end_time": {...}},
    param_model=CutVideoParams,          # Pydantic 校验
    before_execute=validate_video_exists,  # 执行前 Hook
)
async def tool_cut_video(video_id: int, start_time: str = "00:00:00",
                         end_time: str = None, **kwargs) -> Dict[str, Any]:
    ...
```

Hook 机制：`before_execute` 接收 params dict，可校验/修改后返回；`after_execute` 接收 result dict。`react_agent.py` 的 `_execute_tool()` 在执行前后调用。

### 工具注册关键约定
- `cut_video` 执行后会将结果注册为新素材入库（返回新 `video_id`），支持工具链式调用（剪切 → 分析）
- `list_videos` 支持 `project_id` 参数，按项目筛选素材
- `get_video_description` 无描述时提示用户使用 AI 分析
- `analyze_video_vl` 从数据库读取 `video.duration` 传给 VL，约束片段时间戳不超出视频实际时长

### 已注册工具分类
共 63 个工具，按类别：

- **基础视频操作**: cut_video, merge_videos, add_subtitle, change_speed, compress_video, split_video, convert_to_gif, convert_format
- **音频处理**: add_audio, extract_audio, mix_audio_to_video, separate_vocal, normalize_audio, equalize_audio, fade_audio, add_echo, denoise_audio, pitch_shift, reverse_audio
- **AI 能力**: smart_clip, analyze_video, analyze_video_vl, transcribe_video, generate_tts, generate_music, translate_text, detect_language
- **素材管理**: list_videos, get_video_description, search_material, search_files, download_video, delete_material, random_video, set_cover, update_description, list_audios
- **FFmpeg 滤镜**: adjust_brightness, blur_video, sharpen_video, rotate_video, flip_video, crop_video, fade_video, picture_in_picture, add_watermark, add_text_overlay, reverse_video, stabilize_video, scene_detect, slow_motion, color_adjust
- **系统工具**: get_current_time, list_directory, get_system_info, open_folder, task_status, time_convert, srt_to_ass, suggest_music, optimize_prompt, help, extract_frames, get_video_detail, batch_compress

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
- 重试逻辑使用指数退避，同步用 `time.sleep()`，异步用 `await asyncio.sleep()`

## 配置 (.env)

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=http://localhost:9528
API_PORT=9527
```

## 其他约定

- **数据库**: SQLite (`src/db/synthetix.db`)，Alembic `render_as_batch=True` 兼容 SQLite ALTER TABLE
- **FFmpeg**: 二进制文件在 `ffmpeg/` 目录，所有视频处理通过 `subprocess.run(['ffmpeg', ...])` 本地执行，零网络依赖
- **静态文件**: 后端挂载 `/static` 目录，前端通过 `assetUrl(path)` 构建完整 URL
- **VL 视频分析**: `qwen_vl_adapter.py` 中本地文件通过 `_file_to_data_url()` 转 base64 data URL 再发给 core-nexus-ai，不能直接传文件路径。`video_summary()` 接受 `duration` 参数，在 prompt 中约束片段时间戳不超过视频实际时长
- **项目输出视频**: `VideoProject.output_videos` (JSON 数组) 存储渲染输出列表 `[{path, created_at}]`，支持多个输出
- **el-tag type**: 合法值为 `success/warning/danger/info/primary`，不能传空字符串 `''`
- **ErrorBoundary**: `MainLayout.vue` 用 `ErrorBoundary.vue` 包裹 `router-view`
- **工具页面**: TTS/ASR/VL 等工具页通过 `defineAsyncComponent` 懒加载，以 `el-dialog` 弹窗形式打开，不使用独立路由
- **安全**: Pydantic `validate_params` 失败抛异常（不静默返回）；LLM 修正后的参数会重新校验；FFmpeg 字符串参数经 `sanitize_ffmpeg_string()` 清洗
