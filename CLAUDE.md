# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 工作流自动化平台，通过 Web 界面提供各种 AI 功能。集成了多种 AI 服务，包括视频处理、音频生成/语音克隆、字幕转录、翻译和基于 LLM 的内容创作。

## 运行应用

```bash
# 同时启动 API 和 Web UI (推荐)
# API 在 :9527，Web 在 :9528
python run_api.py

# 或单独启动
python run_web.py
```

- API 文档: http://127.0.0.1:9527/docs
- Web 界面: http://127.0.0.1:9528

## 架构

项目采用分层架构（Clean Architecture 风格）：

```
src/
├── domain/              # 领域层
│   └── entities/        # SQLAlchemy 实体定义 (VideoSource, AudioSource)
├── application/         # 应用层
│   └── services/        # 业务服务 (VideoService, fish_voice, use_ffmpeg, etc.)
├── infrastructure/      # 基础设施层
│   ├── db/              # 数据库会话、Alembic 迁移
│   └── repositories/    # Repository 数据访问层 (BaseRepository, VideoRepository)
├── interfaces/          # 接口层
│   └── api/             # FastAPI 路由 (video_api, svc_api, tool_api, llm_clip_api)
└── shared/              # 共享层
    ├── models/          # Pydantic 模型 (request, response)
    ├── utils/           # 工具类 (file_util, ffmpeg_util, task_manager)
    ├── constants.py     # 常量定义
    └── exceptions/      # 异常处理
```

### 关键设计模式

- **Repository 模式**: 数据访问通过 `BaseRepository` 和具体 Repository 类抽象
- **依赖注入**: 数据库会话通过 `get_db()` 注入，Service 通过 `Depends()` 注入
- **统一响应格式**: 使用 `success_response()` 和 `error_response()`

### 添加新功能示例

```python
# 1. 定义实体 (src/domain/entities/)
# 2. 创建 Repository (src/infrastructure/repositories/)
# 3. 创建 Service (src/application/services/)
# 4. 创建 API 路由 (src/interfaces/api/)

# API 层示例
@router.get("/{id}")
def get_item(id: int, service: ItemService = Depends(get_item_service)):
    item = service.repository.get_by_id(id)
    if not item:
        return error_response(error="NotFound", message="不存在", code=404)
    return success_response(data=service.repository.to_dict(item))
```

### 数据库

- **类型**: SQLite (`src/db/synthetix.db`)
- **ORM**: SQLAlchemy
- **迁移**: Alembic（启动时自动应用）
- **创建迁移**: 修改 `src/domain/entities/` 后执行 `alembic revision --autogenerate -m "描述"`

## 配置

环境变量 (`.env`):

```env
LLM_MODEL=deepseek
MODEL_NAME=deepseek-chat
LLM_KEY=your_api_key
VIDEO_API_KEYS=your_video_api_key
CORS_ORIGINS=http://localhost:9528,http://127.0.0.1:9528
PROXY=http://127.0.0.1:7890  # 可选
```

常量定义在 `src/constants.py` 和 `src/shared/constants.py`（文件大小、分页、视频处理参数等）。

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
- **Fish Speech**: 语音克隆/TTS
- **Faster Whisper**: 语音转文字
- **yt-dlp**: 视频下载
- **LangChain**: LLM 集成
- **FFmpeg**: 媒体处理（需在 `ffmpeg/` 文件夹放置二进制文件）

## 重要说明

- FFmpeg 二进制文件必须在 `ffmpeg/` 文件夹
- HuggingFace 模型缓存在 `D:/hf-model/`
- 日志写入 `static/loginfo/`
- 每次启动 API 清空 `static/uploads/`
- API 路由中静态路由必须在动态路由（`/{id}`）之前定义
