# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 工作流自动化平台，通过 Web 界面提供各种 AI 功能。后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、VL 等 AI 服务。

## 运行应用

```bash
# 同时启动 API 和 Web UI (推荐)
# API 在 :9527，Web 在 :9528
python run_api.py

# 或单独启动前端
python run_web.py
```

- API 文档: http://127.0.0.1:9527/docs
- Web 界面: http://127.0.0.1:9528

## 架构

项目采用分层架构（Clean Architecture 风格）：

```
src/
├── domain/              # 领域层
│   └── entities/        # SQLAlchemy 实体 (VideoSource, AudioSource)
├── application/         # 应用层
│   └── services/        # 业务服务 (VideoService, AudioService, CreativeService)
│       ├── llm_adapter.py          # LLM 调用 (通过 core-nexus-ai)
│       ├── fish_speech_adapter.py  # TTS 语音合成 (通过 core-nexus-ai)
│       ├── whisper_adapter.py      # ASR 语音识别 (通过 core-nexus-ai)
│       ├── qwen_vl_adapter.py      # VL 视觉理解 (通过 core-nexus-ai)
│       └── translation_adapter.py  # 翻译服务
├── infrastructure/      # 基础设施层
│   ├── db/              # 数据库会话、Alembic 迁移
│   └── repositories/    # Repository 数据访问层
├── interfaces/          # 接口层
│   └── api/             # FastAPI 路由
│       ├── video_api.py           # /api/videos
│       ├── svc_api.py             # /api/audios
│       ├── tool_api.py            # /api/tools
│       ├── llm_clip_api.py        # /api/ai
│       └── core_nexus_api.py      # /api/nexus (LLM/TTS/ASR/VL)
└── shared/              # 共享层
    ├── models/          # Pydantic 模型
    ├── utils/           # 工具类
    │   └── core_nexus_client.py   # core-nexus-ai HTTP 客户端
    ├── constants.py     # 常量定义
    └── exceptions/      # 异常处理

synthetix-vue/           # 前端 Vue 3 应用
├── src/components/      # 页面组件
│   ├── LLMChat.vue      # LLM 对话 (流式)
│   ├── TTS.vue          # 语音合成
│   ├── ASR.vue          # 语音识别
│   └── VL.vue           # 视觉理解
└── src/layouts/         # 布局组件
```

## Core-Nexus-AI 集成

项目通过 `CoreNexusClient` 调用外部 core-nexus-ai 服务，提供统一推理能力：

| 功能 | API 端点 | 客户端方法 |
|------|----------|-----------|
| LLM 文本生成 | POST /api/nexus/llm | `client.llm_generate()` |
| LLM 流式生成 | POST /api/nexus/llm/stream | `client.llm_generate_stream()` |
| TTS 语音合成 | POST /api/nexus/tts | `client.tts_generate()` |
| ASR 语音识别 | POST /api/nexus/asr | `client.asr_transcribe()` |
| VL 视觉理解 | POST /api/nexus/vl | `client.vl_generate()` |
| VL 流式理解 | POST /api/nexus/vl/stream | `client.vl_generate_stream()` |

## 配置

环境变量 (`.env`):

```env
# core-nexus-ai 配置（必填）
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port

# LLM 配置（保留用于兼容）
LLM_MODEL=deepseek
MODEL_NAME=deepseek-chat
LLM_KEY=your_api_key

# 视频API配置
VIDEO_API_KEYS=your_video_api_key

# CORS配置
CORS_ORIGINS=http://localhost:9528,http://127.0.0.1:9528

# 代理配置（可选）
PROXY=http://127.0.0.1:7890
```

## 测试

```bash
pytest tests/unit/ -v                           # 运行所有单元测试
pytest tests/unit/test_request.py -v            # 运行特定测试
pytest tests/unit/ --cov=src --cov-report=html  # 生成覆盖率报告
```

## 主要依赖

- **FastAPI**: Web 框架
- **SQLAlchemy + Alembic**: ORM 和数据库迁移
- **Pydantic v2**: 请求/响应验证
- **httpx**: HTTP 客户端 (调用 core-nexus-ai)
- **yt-dlp**: 视频下载
- **FFmpeg**: 媒体处理（需在 `ffmpeg/` 文件夹放置二进制文件）

## 重要说明

- FFmpeg 二进制文件必须在 `ffmpeg/` 文件夹
- HuggingFace 模型缓存在 `D:/hf-model/`
- 日志写入 `static/loginfo/`
- 每次启动 API 清空 `static/uploads/`
- API 路由中静态路由必须在动态路由（`/{id}`）之前定义
- 所有 AI 推理通过 core-nexus-ai API，不在本地运行模型
