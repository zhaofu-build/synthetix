# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 视频剪辑平台，提供两种剪辑模式：
1. **对话式 AI 剪辑** - 通过自然语言对话完成视频剪辑
2. **强控制性剪辑** - 分步流程，用户精确控制每一步

后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、VL 等 AI 服务。

## 运行应用

```bash
# 启动 API (端口 9527)
python run_api.py

# 启动前端
cd synthetix-vue && npm run dev
```

- API 文档: http://127.0.0.1:9527/docs
- Web 界面: http://127.0.0.1:9528

## 数据库迁移

```bash
# 生成迁移文件（添加新实体后）
alembic revision --autogenerate -m "描述"

# 执行迁移
alembic upgrade head

# 查看当前版本
alembic current
```

添加新实体后，必须在 `alembic/env.py` 中导入才能被迁移识别。

## 架构

```
src/
├── agent/                    # 对话式剪辑 Agent 模块
│   ├── video_agent.py        # 主 Agent 类
│   ├── session_manager.py    # 会话管理
│   ├── intent_recognizer.py  # 意图识别
│   ├── slot_filler.py        # 槽位填充
│   ├── tool_registry.py      # 工具注册表
│   └── prompts.py            # 提示词模板
│
├── domain/
│   └── entities/             # SQLAlchemy 实体
│       ├── video_source.py   # 视频素材
│       ├── audio_source.py   # 音频素材
│       └── video_project.py  # 视频项目（强控制性剪辑）
│
├── application/services/     # 业务服务
│   ├── video_service.py      # 视频处理
│   ├── audio_service.py      # 音频处理
│   ├── creative_service.py   # 创意内容生成
│   ├── clip_planner.py       # 剪辑方案规划
│   ├── render_service.py     # 视频渲染
│   ├── llm_adapter.py        # LLM 调用
│   ├── ffmpeg_adapter.py     # FFmpeg 封装
│   └── ...
│
├── interfaces/api/           # FastAPI 路由
│   ├── agent_api.py          # /api/agent (对话式剪辑)
│   ├── project_api.py        # /api/projects (强控制性剪辑)
│   ├── core_nexus_api.py     # /api/nexus (AI 服务代理)
│   ├── video_api.py          # /api/videos
│   └── ...
│
├── shared/
│   ├── models/
│   │   ├── timeline.py       # 时间线数据结构
│   │   ├── request.py        # 请求模型
│   │   └── response.py       # 响应模型
│   └── utils/
│       ├── core_nexus_client.py  # core-nexus-ai 客户端
│       └── ...
│
└── infrastructure/
    ├── db/                   # 数据库会话、Alembic
    └── repositories/         # Repository 数据访问层

synthetix-vue/                # 前端 Vue 3 应用
├── src/components/
│   ├── AIClip.vue            # 对话式剪辑界面
│   ├── VideoStitching.vue    # 强控制性剪辑界面
│   └── ...
└── src/api/modules/          # API 模块
```

## 对话式剪辑 Agent

Agent 模块实现自然语言视频剪辑：

```
用户消息 → 意图识别 → 槽位填充 → 方案确认 → 工具执行 → 返回结果
```

**意图类型**：cut_video, merge_videos, add_subtitle, add_audio, change_speed, smart_clip, analyze_video, generate_tts, list_videos, search_material

**工具注册**：使用装饰器 `@registry.register()` 注册新工具

## Core-Nexus-AI 集成

所有 AI 推理通过 `CoreNexusClient` 调用外部服务：

| 功能 | 方法 |
|------|------|
| LLM 生成 | `client.llm_generate()` |
| LLM 流式 | `client.llm_generate_stream()` |
| TTS 合成 | `client.tts_generate()` |
| ASR 识别 | `client.asr_transcribe()` |
| VL 理解 | `client.vl_generate()` |
| 音乐生成 | `client.text_to_music()` |

## 配置 (.env)

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=http://localhost:9528
```

## 测试

```bash
pytest tests/unit/ -v                           # 运行单元测试
pytest tests/unit/test_xxx.py -v                # 运行单个测试
pytest tests/unit/ --cov=src --cov-report=html  # 覆盖率报告
```

## 重要约定

- **命名转换**：后端使用 snake_case，通过 `success_response(to_camel=True)` 自动转为 camelCase 返回前端
- **路由顺序**：静态路由必须在动态路由（`/{id}`）之前定义
- **FFmpeg**：二进制文件必须在 `ffmpeg/` 文件夹
- **数据库**：SQLite，路径 `src/db/synthetix.db`
- **新实体**：添加后必须在 `alembic/env.py` 导入并运行迁移

## 前端 API 调用

```javascript
import { videoApi, aiApi, assetUrl, API_HOST } from '@/api/modules'

// 使用封装的方法
const data = await videoApi.upload(file)

// 直接调用 Agent API
const response = await fetch(`${API_HOST}/api/agent/chat`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ session_id, message })
})
```
