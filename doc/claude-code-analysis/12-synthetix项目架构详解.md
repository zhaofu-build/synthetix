# 12 - Synthetix 项目架构详解

## 概述

Synthetix 是一个 AI 视频剪辑平台，后端所有 AI 推理通过统一的 `CoreNexusClient` 调用 **core-nexus-ai** 服务完成。本文档详细剖析 synthetix 的分层架构、core-nexus-ai 集成方式、Agent 对话系统、以及从前端到 AI 服务的完整数据流。

## 项目技术栈

| 层面 | 技术 | 说明 |
|------|------|------|
| 后端框架 | **FastAPI** | Python 异步 Web 框架，端口 9527 |
| 前端框架 | **Vue 3 + Vite + Pinia + Element Plus** | 端口 9528 |
| 数据库 | **SQLite + SQLAlchemy** | `src/db/synthetix.db`，Alembic 迁移 |
| AI 服务 | **core-nexus-ai** | 独立服务，端口 9666，提供 LLM/TTS/ASR/VL 等 |
| HTTP 客户端 | **httpx** | 调用 core-nexus-ai REST API |
| 视频处理 | **FFmpeg** | `ffmpeg/` 目录下的二进制文件 |

## 分层架构

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         前端（Vue 3 + Vite）                              │
│  AIClip.vue（对话剪辑）    VideoStitching.vue（工作流剪辑）  ProjectList.vue │
│          │                          │                           │         │
│  src/api/modules/ai.js      src/api/modules/video.js    src/api/modules/  │
│          │                          │                       project.js     │
├──────────┼──────────────────────────┼───────────────────────────┼─────────┤
│          │         FastAPI 后端（端口 9527）                      │         │
│          ▼                          ▼                           ▼         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  ┌────────────────┐  │
│  │ agent_api    │  │ video_api    │  │ project  │  │ core_nexus_api │  │
│  │ /api/agent   │  │ /api/videos  │  │ /api/    │  │ /api/nexus     │  │
│  │              │  │              │  │ projects │  │ (AI 服务代理)   │  │
│  └──────┬───────┘  └──────┬───────┘  └────┬─────┘  └───────┬────────┘  │
│         │                 │                │                 │            │
│  ┌──────┴───────┐  ┌─────┴────────┐  ┌───┴──────┐   ┌─────┴────────┐  │
│  │   Agent 层    │  │  Service 层  │  │  Repo    │   │  CoreNexus   │  │
│  │ video_agent   │  │ video_svc    │  │  层      │   │  Client      │  │
│  │ intent_reco   │  │ clip_planner │  │          │   │  (统一客户端)  │  │
│  │ slot_filler   │  │ creative_svc │  │          │   │              │  │
│  │ tool_registry │  │ llm_adapter  │  │          │   │              │  │
│  │ session_mgr   │  │              │  │          │   │              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┘   └──────┬───────┘  │
│         │                 │                                  │           │
│  ┌──────┴─────────────────┴──────────────────────────────────┴──────┐  │
│  │                    Domain / Infrastructure 层                      │  │
│  │   entities(video_source, audio_source, video_project, bgm_item)   │  │
│  │   db/session.py · repositories/ · alembic/                        │  │
│  └───────────────────────────────────────────────────────────────────┘  │
├──────────────────────────────────────────────────────────────────────────┤
│                         core-nexus-ai（独立服务，端口 9666）                │
│          LLM · TTS · ASR · VL · OCR · 文生图 · 文生视频 · 音乐           │
└──────────────────────────────────────────────────────────────────────────┘
```

## core-nexus-ai 集成

### 连接配置

```env
# .env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:9666
LLM_KEY=your_api_key
```

### CoreNexusClient（核心客户端）

所有 AI 调用的统一入口，位于 `src/shared/utils/core_nexus_client.py`：

```python
class CoreNexusClient:
    def __init__(self, base_url=None, timeout=120.0):
        self.base_url = (base_url or config.CORE_NEXUS_BASE_URL).rstrip('/')
        self.timeout = timeout

    # 通用请求方法
    def _request(self, method, endpoint, json_data=None, **kwargs) -> Dict
    def _request_stream(self, method, endpoint, json_data=None, **kwargs) -> Generator

    # AI 能力方法
    def llm_generate(messages, model, temperature, max_tokens) -> str
    def llm_generate_stream(messages, ...) -> Generator[str]
    def tts_generate(text, speaker, ref_audio, ...) -> bytes
    def asr_transcribe(audio, language, ...) -> Dict
    def vl_generate(prompt, image, video, ...) -> str
    def vl_generate_stream(prompt, ...) -> Generator[str]
    def text_to_music(prompt, duration, style, ...) -> Dict
```

### API 调用映射

| 业务方法 | core-nexus-ai 端点 | 请求格式 | 响应提取 |
|----------|-------------------|----------|----------|
| `llm_generate()` | `POST /llm` | `{messages, generation:{temperature,max_tokens}}` | `response.output.text` |
| `llm_generate_stream()` | `POST /llm/stream` | 同上（SSE） | `chunk.text` |
| `tts_generate()` | `POST /tts` | `{text, speaker, language, ...}` | 音频二进制 |
| `asr_transcribe()` | `POST /asr` | `{audio, language}` | `response.output` |
| `vl_generate()` | `POST /vl` | `{prompt, image, video, ...}` | `response.output.text` |
| `vl_generate_stream()` | `POST /vl/stream` | 同上（SSE） | `chunk.text` |
| `text_to_music()` | `POST /text-to-music` | `{prompt, duration, style}` | `response.output` |

### 请求格式关键点

```python
# temperature/max_tokens 必须嵌套在 generation 对象中
payload = {
    "messages": [{"role": "user", "content": "..."}],
    "model": "qwen-plus",              # 可选
    "generation": {
        "temperature": 0.7,
        "max_tokens": 2048
    }
}

# 响应格式
response = {
    "output": {"text": "生成的内容"},
    "model": "qwen-plus",
    "usage": {"prompt_tokens": 100, "completion_tokens": 200}
}
```

### 媒体数据处理

`CoreNexusClient` 内置媒体数据自动转换：

| 输入类型 | 转换方式 |
|----------|----------|
| 文件路径 | 读取文件 → base64 → `data:mime/type;base64,...` |
| 纯 base64 | 添加 `data:audio/wav;base64,...` 前缀 |
| data URL | 直接使用 |
| HTTP URL | 直接传递（由 core-nexus-ai 处理） |

## 两条 AI 调用路径

synthetix 中有两条不同的路径调用 core-nexus-ai：

### 路径 1：Agent 对话剪辑（通过 Agent 层）

```
用户对话 → Agent → 意图识别/槽位填充 → 工具执行 → 结果
```

**调用链：**

```
AIClip.vue (sendMessage)
  ↓ fetch POST /api/agent/chat
agent_api.py (chat endpoint)
  ↓ get_video_agent().process_message()
VideoDialogAgent.process_message()
  ↓
IntentRecognizer.recognize()
  ↓ generate_response()        ← 同步调用
  ↓ CoreNexusClient.llm_generate()  ← POST /llm
  ↓ core-nexus-ai
  ↓ 返回意图 JSON
  ↓
SlotFiller.fill()
  ↓ generate_response()        ← 同步调用（如需 LLM 提取）
  ↓ CoreNexusClient.llm_generate()  ← POST /llm
  ↓ core-nexus-ai
  ↓ 返回槽位 JSON
  ↓
用户确认 → ToolRegistry.get_tool().execute()
  ↓ 工具内部可能调用 CoreNexusClient（如 analyze_video 用 VL）
  ↓
结果返回前端
```

**特点：** 每轮对话可能调用 core-nexus-ai **1-2 次**（意图识别 + 槽位提取）。

### 路径 2：直接 AI 代理（通过 core_nexus_api.py）

```
前端 → /api/nexus/xxx → CoreNexusClient → core-nexus-ai
```

**调用链：**

```
Vue 前端 (api/modules/ai.js)
  ↓ axios POST /api/nexus/llm
core_nexus_api.py (llm_generate endpoint)
  ↓ get_client().llm_generate()
CoreNexusClient.llm_generate()
  ↓ POST /llm
core-nexus-ai
  ↓
结果返回前端
```

**特点：** 纯透传代理，前端直接使用 AI 能力。支持 LLM/TTS/ASR/VL/音乐 的全部端点。

## Agent 对话系统详解

### 状态机

```
IDLE（空闲）
  ↓ 收到用户输入
  ↓ 意图识别
COLLECTING（收集信息）
  ↓ 槽位填充
  ↓ 所有必填槽位已填充
CONFIRMING（等待确认）
  ↓ 用户说"确认"
EXECUTING（执行中）
  ↓ 工具执行完成
COMPLETED / ERROR
  ↓ 重置
IDLE
```

### 意图类型（10 + 3）

| 业务意图 | 说明 | 必填槽位 |
|----------|------|----------|
| `cut_video` | 剪切视频片段 | `video_id` |
| `merge_videos` | 合并多个视频 | `video_ids` |
| `add_subtitle` | 添加字幕 | `video_id` |
| `add_audio` | 添加音频/配音 | `video_id` |
| `change_speed` | 调整播放速度 | `video_id`, `speed_factor` |
| `smart_clip` | AI 智能剪辑 | `description` |
| `analyze_video` | 分析视频内容 | `video_id` |
| `generate_tts` | 文字转语音 | `text` |
| `list_videos` | 查看素材列表 | （无） |
| `search_material` | 搜索素材 | `keywords` |

| 系统意图 | 说明 |
|----------|------|
| `confirm` | 用户确认执行 |
| `cancel` | 用户取消操作 |
| `help` | 获取帮助 |

### 意图识别流程

```
用户输入
  ↓
快速规则匹配（_quick_match）
  ├── "确认/好的/是" → confirm
  ├── "取消/不要/否" → cancel
  ├── "帮助/help" → help
  ├── "素材/视频列表" → list_videos
  └── 无命中 ↓
LLM 意图识别（_llm_recognize）
  ├── 构建 Prompt（含全部意图描述 + 对话历史 + 当前视频）
  ├── generate_response(messages) → CoreNexusClient.llm_generate()
  ├── 解析 JSON 响应
  └── 返回 IntentResult{intent, confidence, entities, need_clarification}
```

### 槽位填充流程

```
需要填充的槽位
  ↓
规则提取（_rule_extract）
  ├── "前30秒" → start_time="00:00:00", end_time="00:00:30"
  ├── "慢放/减速" → speed_factor=0.5
  ├── "2倍速" → speed_factor=2.0
  ├── "下载XX素材" → keywords="XX"
  └── 规则未匹配 ↓
LLM 提取（_llm_extract）
  ├── 构建 Prompt（含槽位名+描述+已填充值）
  ├── generate_response(messages) → CoreNexusClient.llm_generate()
  └── 解析 JSON 响应 {"字段名": "值"}
```

## 服务层的 AI 调用

### LLM Adapter（`src/application/services/llm_adapter.py`）

`generate_response()` 是最常用的 AI 调用封装，Agent 层（意图识别、槽位填充）直接调用它：

```python
def generate_response(messages, model_name=None, temperature=0.7, max_tokens=2048) -> str:
    client = get_client()
    return client.llm_generate(messages=messages, model=model_name,
                                temperature=temperature, max_tokens=max_tokens)
```

**调用关系：**
```
IntentRecognizer._llm_recognize()  → generate_response()  → CoreNexusClient.llm_generate()
SlotFiller._llm_extract()          → generate_response()  → CoreNexusClient.llm_generate()
ClipPlanner.plan()                  → generate_response()  → CoreNexusClient.llm_generate()
CreativeService.*()                 → generate_response()  → CoreNexusClient.llm_generate()
```

### Clip Planner（`src/application/services/clip_planner.py`）

使用 LLM 根据用户描述生成剪辑方案：

```
用户描述 "做一个30秒的动感混剪"
  ↓
generate_response() → core-nexus-ai
  ↓
返回 ClipPlan（JSON 结构，包含各片段的时间、素材、转场等）
```

### Creative Service（`src/application/services/creative_service.py`）

创意内容生成，包括关键词提取、素材匹配等，同样通过 `generate_response()` 调用 LLM。

## API 路由层

### Agent API（`/api/agent`）

| 端点 | 方法 | 功能 | 调用 core-nexus-ai |
|------|------|------|-------------------|
| `/api/agent/chat` | POST | 对话式剪辑 | 是（意图识别 + 槽位填充） |
| `/api/agent/chat/stream` | POST | 流式对话 | 是（同上，SSE 返回） |
| `/api/agent/execute` | POST | 直接执行工具 | 视工具而定 |
| `/api/agent/analyze/{id}` | POST | 分析视频 | 是（VL） |
| `/api/agent/tools` | GET | 工具列表 | 否 |
| `/api/agent/session/{id}` | DELETE | 删除会话 | 否 |
| `/api/agent/sessions` | GET | 会话列表 | 否 |

### Core-Nexus API（`/api/nexus`）— AI 服务代理

| 端点 | 方法 | 功能 | 透传到 core-nexus-ai |
|------|------|------|---------------------|
| `/api/nexus/llm` | POST | LLM 文本生成 | `/llm` |
| `/api/nexus/llm/stream` | POST | LLM 流式生成 | `/llm/stream` |
| `/api/nexus/tts` | POST | 文字转语音 | `/tts` |
| `/api/nexus/tts/upload` | POST | TTS + 参考音频上传 | `/tts` |
| `/api/nexus/asr` | POST | 语音识别 | `/asr` |
| `/api/nexus/asr/upload` | POST | ASR + 音频上传 | `/asr` |
| `/api/nexus/vl` | POST | 视觉理解 | `/vl` |
| `/api/nexus/vl/stream` | POST | VL 流式 | `/vl/stream` |
| `/api/nexus/vl/upload` | POST | VL + 图片上传 | `/vl` |
| `/api/nexus/music` | POST | 文生音乐 | `/text-to-music` |

## 完整数据流示例

### 示例 1：对话式剪辑"帮我把视频前30秒剪出来"

```
[前端] AIClip.vue: 用户输入 "帮我把视频前30秒剪出来"
  ↓
[HTTP] POST /api/agent/chat { message: "帮我把视频前30秒剪出来", session_id: null }
  ↓
[Agent] VideoDialogAgent.process_message()
  ↓
[Session] SessionManager.get_or_create_session() → 创建新会话
  ↓
[Intent] IntentRecognizer.recognize()
  ├── 快速匹配: 无命中
  └── LLM 识别:
      └── generate_response() → CoreNexusClient.llm_generate()
          └── POST http://core-nexus:9666/llm { messages, generation: {temp:0.7} }
          └── 返回: {"intent":"cut_video","confidence":0.95,"entities":{"end_time":"00:00:30"}}
  ↓
[Slot] SlotFiller.fill()
  ├── 规则提取: "前30秒" → start_time="00:00:00", end_time="00:00:30"
  └── 缺少 video_id → 自动从 context 填充
  ↓
[Confirm] 返回前端: "请确认：**剪切视频** - 开始时间: 00:00:00 - 结束时间: 00:00:30"
  ↓
[前端] 用户回复 "确认"
  ↓
[HTTP] POST /api/agent/chat { message: "确认", session_id: "xxx" }
  ↓
[Agent] _handle_confirming() → 确认 → _execute_action()
  ↓
[Tool] cut_video 工具执行 → FFmpeg 剪切
  ↓
[Result] "✅ 剪切完成" → 返回前端
```

**core-nexus-ai 调用次数：1 次**（意图识别，槽位通过规则提取未调 LLM）

### 示例 2：通过 AI 代理直接使用 LLM

```
[前端] 直接调用 LLM
  ↓
[HTTP] POST /api/nexus/llm { prompt: "描述这个视频的风格", messages: [...] }
  ↓
[API] core_nexus_api.py → get_client().llm_generate(messages)
  ↓
[Client] POST http://core-nexus:9666/llm { messages, generation }
  ↓
[core-nexus-ai] 返回 { output: { text: "这个视频..." } }
  ↓
[前端] 收到 AI 生成文本
```

**core-nexus-ai 调用次数：1 次**（纯透传）

## 命名转换约定

后端 → 前端的数据转换通过 `success_response(to_camel=True)` 自动完成：

```
后端 snake_case              前端 camelCase
─────────────────────────────────────────
video_id           →         videoId
start_time         →         startTime
target_duration    →         targetDuration
clip_plan          →         clipPlan
material_ids       →         materialIds
```

前端 `debounceSave` 发送 snake_case key，后端 Pydantic 模型匹配 snake_case。

## 配置与环境

```env
# .env 核心配置
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:9666   # AI 服务地址
LLM_KEY=your_api_key                                        # API Key
LLM_MODEL=qwen-plus                                         # 默认模型
CORS_ORIGINS=http://localhost:9528                           # 前端地址
API_PORT=9527                                                # 后端端口
```

## 项目目录结构

```
src/
├── agent/                           # 对话式剪辑 Agent
│   ├── video_agent.py               # 主 Agent（状态机：IDLE→COLLECTING→CONFIRMING→EXECUTING）
│   ├── tool_registry.py             # @registry.register() 注册工具
│   ├── intent_recognizer.py         # 意图识别（规则匹配 + LLM）
│   ├── slot_filler.py               # 槽位填充（正则提取 + LLM）
│   ├── session_manager.py           # 会话管理（内存，DialogState）
│   └── prompts.py                   # Agent 提示词模板
│
├── application/services/            # 业务服务层
│   ├── llm_adapter.py               # LLM 调用封装（→ CoreNexusClient）
│   ├── clip_planner.py              # AI 剪辑方案规划（→ LLM）
│   ├── creative_service.py          # 创意内容生成（→ LLM）
│   ├── video_service.py             # 视频处理（FFmpeg）
│   ├── audio_service.py             # 音频处理
│   └── render_service.py            # 视频渲染
│
├── interfaces/api/                  # FastAPI 路由
│   ├── agent_api.py                 # /api/agent（对话剪辑）
│   ├── core_nexus_api.py            # /api/nexus（AI 服务代理）
│   ├── project_api.py               # /api/projects（项目管理）
│   ├── video_api.py                 # /api/videos（视频 CRUD）
│   ├── audio_api.py                 # /api/audios（音频 CRUD）
│   └── llm_clip_api.py              # /api/ai（LLM 创意剪辑）
│
├── shared/
│   ├── models/response.py           # success_response(to_camel=True)
│   ├── models/timeline.py           # Timeline/ClipPlan 数据结构
│   └── utils/core_nexus_client.py   # ★ CoreNexusClient 统一客户端
│
├── domain/entities/                 # SQLAlchemy 实体
│   ├── video_source.py              # 视频素材
│   ├── audio_source.py              # 音频素材
│   ├── video_project.py             # 视频项目 + ClipPlanItem
│   └── bgm_item.py                  # BGM 素材
│
└── infrastructure/
    ├── db/                          # 数据库会话、Alembic
    └── repositories/                # Repository 数据访问层
```

## 各层代码职责总结

项目不依赖外部 Agent 框架，所有 Agent 能力（工具注册、意图识别、槽位填充、会话管理、状态机）均在 `src/agent/` 目录内直接实现：

```
src/agent/                     项目内自包含的 Agent 系统
├── video_agent.py             状态机编排（IDLE→COLLECTING→CONFIRMING→EXECUTING）
├── tool_registry.py           @registry.register() 装饰器注册业务工具
├── intent_recognizer.py       规则快速匹配 + LLM 意图分类
├── slot_filler.py             正则提取 + LLM 槽位填充
├── session_manager.py         内存会话管理（DialogState）
└── prompts.py                 意图识别/槽位填充的 Prompt 模板
```

```
src/application/services/      AI 调用封装层
├── llm_adapter.py             generate_response() → CoreNexusClient.llm_generate()
├── clip_planner.py             剪辑方案规划 → LLM
└── creative_service.py         创意内容生成 → LLM
```

```
src/shared/utils/
└── core_nexus_client.py       统一 HTTP 客户端 → core-nexus-ai 服务
```

**调用层次：** Agent 层 → `llm_adapter.generate_response()` → `CoreNexusClient.llm_generate()` → core-nexus-ai `/llm` 端点

---

## Claude Code 优化借鉴分析

对照 Claude Code 的 11 个技术模块，逐项评估对 synthetix 的适用性和改造建议。按**优先级**排序：立即可做 > 值得做 > 暂不需要。

### 总览

| Claude Code 模块 | 适用性 | 优先级 | 现状痛点 |
|------------------|--------|--------|----------|
| 02-Agent 运行时 | **高** | P0 | Agent 无循环纠错，失败即终止 |
| 05-记忆与上下文 | **高** | P0 | 会话纯内存，重启丢失；无上下文压缩 |
| 03-工具系统 | **高** | P1 | 工具无参数校验、无执行策略 |
| 11-工程化实践 | **中** | P1 | 无重试、无缓存、CoreNexusClient 同步阻塞 |
| 10-代码转换管道 | **中** | P1 | LLM 输出无验证修正循环 |
| 09-Hook 系统 | **中** | P2 | 工具执行前后无拦截（如自动格式化、日志） |
| 06-权限与安全 | **中** | P2 | 工具参数无校验，FFmpeg 命令无过滤 |
| 08-Skills 系统 | **低** | P3 | 暂无复用需求 |
| 07-多智能体协作 | **低** | P3 | 单用户场景，暂不需要 |
| 04-MCP 协议 | **低** | P3 | 只有 core-nexus-ai 一个外部服务 |
| 01-系统架构 | 参考 | — | 已是分层架构，无需大改 |

---

### P0：立即需要优化

#### 1. Agent 循环纠错（借鉴 02-Agent运行时机制）

**现状问题：**

`video_agent.py` 的状态机是**单程线性**的：IDLE → COLLECTING → CONFIRMING → EXECUTING。工具执行失败后直接返回错误，不会自动重试或调整参数。

```python
# 当前：失败即终止
result = await tool.execute(**params)
if result.get("success"):
    reply = f"✅ {result['message']}"
else:
    reply = f"❌ 执行失败：{result['error']}"  # 就停在这了
```

**借鉴 Claude Code 的做法：**

Claude Code 的 TAOR 循环会自动观察错误结果，将错误反馈回模型，让模型决定下一步（重试/换参数/放弃）。

**建议改造：**

```python
async def _execute_action(self, action, max_retries=2):
    for attempt in range(max_retries + 1):
        result = await tool.execute(**params)
        if result.get("success"):
            return result

        if attempt < max_retries:
            # 将错误反馈给 LLM，让它调整参数重试
            retry_prompt = f"工具执行失败：{result['error']}。请调整参数重试。"
            adjusted = await self.llm_adjust_params(action, result["error"])
            if adjusted:
                action["params"].update(adjusted)
                continue

        return result  # 最终仍失败则返回
```

**改造文件：** `src/agent/video_agent.py` 的 `_execute_action()` 方法。

---

#### 2. 会话持久化 + 上下文压缩（借鉴 05-记忆与上下文管理）

**现状问题：**

`session_manager.py` 是纯内存存储：
- 服务重启 → 所有会话丢失
- 长对话 → `history` 列表无限增长，传给 LLM 的 token 越来越多
- 无过期清理机制（`cleanup_expired_sessions` 存在但从未被调用）

```python
# 当前：history 无限增长
class DialogState:
    history: List[Dict[str, str]] = field(default_factory=list)  # 只增不减
```

**借鉴 Claude Code 的做法：**

Claude Code 用五级压缩 + 三层记忆解决上下文窗口问题。

**建议改造（渐进式）：**

**第一步：对话历史截断**（最小改动）

```python
class DialogState:
    MAX_HISTORY = 20  # 保留最近 20 条

    def add_message(self, role, content):
        self.history.append({"role": role, "content": content})
        if len(self.history) > self.MAX_HISTORY:
            self.history = self.history[-self.MAX_HISTORY:]
        self.updated_at = time.time()
```

**第二步：会话持久化到数据库**

```python
class SessionManager:
    async def save_session(self, state: DialogState):
        """保存到 SQLite，服务重启不丢失"""
        ...

    async def load_session(self, session_id: str) -> Optional[DialogState]:
        """从数据库加载历史会话"""
        ...
```

**第三步：定期清理**

```python
# 在 main.py 启动时注册定时任务
@app.on_event("startup")
async def start_cleanup_task():
    async def cleanup_loop():
        while True:
            await asyncio.sleep(300)  # 每 5 分钟
            manager = get_session_manager()
            cleaned = manager.cleanup_expired_sessions()
            if cleaned:
                logger.info(f"清理了 {cleaned} 个过期会话")
    asyncio.create_task(cleanup_loop())
```

**改造文件：** `src/agent/session_manager.py`、`main.py`

---

### P1：值得优化

#### 3. 工具参数校验（借鉴 03-工具系统）

**现状问题：**

`tool_registry.py` 的工具参数只有字典描述，**无运行时校验**。LLM 提取的槽位值可能类型错误（如 `video_id` 传了字符串、`speed_factor` 传了负数）。

```python
# 当前：parameters 只是描述，不校验
parameters={
    "video_id": {"type": "integer", "description": "视频 ID"},  # 仅文档用途
    "speed_factor": {"type": "number", "description": "速度倍数"},
}
```

**借鉴 Claude Code 的做法：**

Claude Code 用 Zod Schema 做运行时参数校验。Python 中对应的是 Pydantic。

**建议改造：**

```python
from pydantic import BaseModel, Field, validator

class CutVideoParams(BaseModel):
    video_id: int = Field(..., gt=0, description="视频 ID")
    start_time: str = Field("00:00:00", pattern=r"^\d{2}:\d{2}:\d{2}$")
    end_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}:\d{2}$")

    @validator("end_time")
    def end_after_start(cls, v, values):
        # 校验结束时间 > 开始时间
        ...

# 工具执行前校验
async def _execute_action(self, action):
    tool = registry.get_tool(action["tool"])
    try:
        validated = tool.params_model(**action["params"])  # Pydantic 校验
        result = await tool.execute(**validated.dict())
    except ValidationError as e:
        return {"success": False, "error": f"参数错误: {e}"}
```

**改造文件：** `src/agent/tool_registry.py`

---

#### 4. CoreNexusClient 异步化 + 重试（借鉴 11-工程化实践）

**现状问题：**

`core_nexus_client.py` 使用**同步** `httpx.Client`，会阻塞 FastAPI 的事件循环：

```python
# 当前：同步请求，阻塞事件循环
def _request(self, method, endpoint, json_data=None, **kwargs):
    with httpx.Client() as client:          # 同步
        response = client.request(...)       # 阻塞
        return response.json()
```

`llm_adapter.py` 的 `generate_response()` 也是同步函数，但被 `IntentRecognizer` 和 `SlotFiller` 的 `async` 方法调用。

**建议改造：**

```python
class CoreNexusClient:
    # 改为异步
    async def _request(self, method, endpoint, json_data=None, **kwargs):
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, json=json_data, **kwargs)
            response.raise_for_status()
            return response.json()

    async def llm_generate(self, messages, model=None, ...):
        response = await self._request('POST', '/llm', json_data=payload)
        return response.get('output', {}).get('text', '')

    # 加重试
    async def _request_with_retry(self, method, endpoint, json_data=None,
                                   max_retries=2, **kwargs):
        for attempt in range(max_retries + 1):
            try:
                return await self._request(method, endpoint, json_data, **kwargs)
            except httpx.TimeoutException:
                if attempt == max_retries:
                    raise
                await asyncio.sleep(1 * (attempt + 1))  # 退避
```

`llm_adapter.py` 对应改为 `async def generate_response()`，调用链上层的 `IntentRecognizer`、`SlotFiller` 前面已经有 `await`，改动最小。

**改造文件：** `src/shared/utils/core_nexus_client.py`、`src/application/services/llm_adapter.py`

---

#### 5. LLM 输出验证修正（借鉴 10-代码转换管道）

**现状问题：**

`intent_recognizer.py` 和 `slot_filler.py` 解析 LLM 的 JSON 输出时，解析失败直接返回 `unknown` 意图或空槽位，**不会重试**：

```python
# 当前：JSON 解析失败就放弃
try:
    result = json.loads(response)
    return IntentResult.from_dict(result)
except json.JSONDecodeError as e:
    return IntentResult(intent="unknown", ...)  # 放弃
```

**借鉴 Claude Code 的做法：**

Claude Code 的代码转换管道有**最多 3 次修正循环**。

**建议改造：**

```python
async def _llm_recognize(self, user_input, history, current_video, max_retries=2):
    prompt = self.prompts.format_intent_prompt(...)

    for attempt in range(max_retries + 1):
        try:
            response = generate_response([{"role": "user", "content": prompt}])
            response = self._clean_json_response(response)
            return IntentResult.from_dict(json.loads(response))
        except (json.JSONDecodeError, KeyError) as e:
            if attempt < max_retries:
                # 将错误信息反馈给 LLM 重试
                prompt += f"\n\n上次返回的 JSON 格式有误: {e}，请重新返回正确 JSON。"
                continue
            return IntentResult(intent="unknown", ...)

def _clean_json_response(self, response: str) -> str:
    """清理 LLM 返回的 JSON（去 markdown 标记等）"""
    response = response.strip()
    if response.startswith("```"):
        response = response.split("\n", 1)[1]
    if response.endswith("```"):
        response = response.rsplit("```", 1)[0]
    return response.strip()
```

**改造文件：** `src/agent/intent_recognizer.py`、`src/agent/slot_filler.py`

---

### P2：按需优化

#### 6. Hook 机制（借鉴 09-插件与Hook系统）

**适用场景：** 工具执行前后的通用逻辑（日志、参数修正、结果后处理）。

**建议：** 在 `_execute_action()` 中加入钩子点：

```python
async def _execute_action(self, action):
    # before hook
    action = await self._run_hooks("before", action)

    result = await tool.execute(**action["params"])

    # after hook
    result = await self._run_hooks("after", action, result)
    return result
```

用例示例：
- `before` hook：校验 video_id 对应的视频是否存在（统一前置检查，不用每个工具重复写）
- `after` hook：执行成功后自动将输出文件注册到数据库

---

#### 7. 安全加固（借鉴 06-权限与安全系统）

**现状风险：** 工具参数中可能混入恶意 FFmpeg 命令参数。

**建议（轻量版）：**

```python
# tool_registry.py 中加入参数清洗
class ToolRegistry:
    def sanitize_params(self, params: dict) -> dict:
        """清洗工具参数，防止注入"""
        cleaned = {}
        for key, value in params.items():
            if isinstance(value, str):
                # 过滤 FFmpeg 命令注入字符
                value = value.replace(";", "").replace("|", "").replace("&", "")
            cleaned[key] = value
        return cleaned
```

---

### P3：暂不需要

| Claude Code 模块 | 原因 |
|------------------|------|
| **07-多智能体协作** | synthetix 是单用户视频剪辑，无需多 Agent 并行。若未来做"团队协作剪辑"可考虑 |
| **04-MCP 协议** | synthetix 只对接 core-nexus-ai 一个 AI 服务，HTTP 直连足够。若未来需要接入多个外部工具服务（如 Pexels 素材 API、字幕生成服务等）再引入 |
| **08-Skills 系统** | 当前项目只有视频剪辑一个领域，工具和 Prompt 数量有限，不需要 Skill 打包。若未来扩展到其他创作领域（音频编辑、图片处理），可借鉴 |

---

### 优化路线图

```
阶段 1（1-2 天）— 修复痛点
├── Agent 循环纠错（P0-1）
├── 对话历史截断（P0-2 第一步）
└── LLM 输出重试（P1-5）

阶段 2（3-5 天）— 质量提升
├── CoreNexusClient 异步化（P1-4）
├── 工具参数 Pydantic 校验（P1-3）
└── 会话定时清理（P0-2 第三步）

阶段 3（按需）— 扩展能力
├── Hook 机制（P2-6）
├── 安全加固（P2-7）
└── 会话持久化到数据库（P0-2 第二步）
```

> **相关文档：**
> - 多项目分层架构方案详见 [项目分层架构方案.md](项目分层架构方案.md)
> - Claude Code 的 Agent 循环机制对比详见 [02-Agent运行时机制](02-Agent运行时机制.md)
> - Claude Code 的记忆管理对比详见 [05-记忆与上下文管理](05-记忆与上下文管理.md)
> - Claude Code 的工具校验对比详见 [03-工具系统](03-工具系统.md)
