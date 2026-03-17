# CLAUDE.md

此文件为 Claude Code (claude.ai/code) 提供在此仓库中工作的指导。

## 项目概述

Synthetix 是一个 AI 工作流自动化平台，通过 Web 界面提供各种 AI 功能。集成了多种 AI 服务，包括视频处理、音频生成/语音克隆、字幕转录、翻译和基于 LLM 的内容创作。

## 运行应用

### 启动服务

```bash
# 仅启动 API (端口 9527)
python run_api.py

# 仅启动 Web UI (端口 9528) - 需要单独运行 API
python run_web.py

# 同时启动 API 和 Web UI (推荐)
# 这会启动 API 在 :9527，Web 在 :9528，并自动打开浏览器
python run_web.py  # 此命令会同时启动两个进程
```

### 访问地址

- API 文档: http://127.0.0.1:9527/docs (Swagger UI)
- Web 界面: http://127.0.0.1:9528

## 架构

### 后端结构

```
src/
├── api/           # FastAPI 路由处理器
│   ├── svc_api.py      # 语音克隆、音频处理接口
│   ├── video_api.py    # 视频下载和处理
│   ├── tool_api.py     # 工具类接口
│   └── llm_clip_api.py # LLM 对话和视频剪辑
├── service/       # 业务逻辑层
│   ├── fish_voice.py      # Fish Speech TTS
│   ├── video_downloader.py # yt-dlp 视频下载
│   ├── use_fast_whisper.py # 字幕转录
│   ├── use_ffmpeg.py      # FFmpeg 操作
│   ├── use_translation.py # 翻译服务
│   └── use_langchain_llm.py # LLM 集成
├── db/            # 数据库层
│   ├── session.py          # SQLAlchemy 会话管理
│   └── alembic_manager.py  # 数据库迁移工具
├── model/         # 数据模型
│   ├── base.py            # Pydantic 模型 + SQLAlchemy Base
│   └── entity/            # SQLAlchemy 实体定义
└── util/          # 工具类 (FFmpeg、文件操作等)
```

### 关键设计模式

- **依赖注入**: 数据库会话通过 `get_db()` 依赖注入
- **关注点分离**: 路由在 `api/`，业务逻辑在 `service/`
- **静态文件**: 从 `static/` 目录提供（上传文件、日志、素材等）
- **自动初始化**: API 启动时自动运行 Alembic 数据库迁移

### 数据库

- **类型**: SQLite (`src/db/we_library.db`)
- **ORM**: SQLAlchemy
- **迁移**: Alembic（启动时自动应用）
- **创建新迁移**: 修改 `src/model/entity/` 中的模型，然后执行 `alembic revision --autogenerate -m "描述"`

### 前端

- 已构建的前端文件位于 `dist/` 目录
- SPA 使用 history 模式路由（404 会回退到 index.html）

## 配置

所有配置位于 `config.py`：
- `api_host` (9527)、`web_host` (9528): 服务端口
- `MODEL_CACHE_DIR`: HuggingFace 模型缓存位置
- `UPLOAD_DIR`、`source_*_dir`: 静态文件目录
- LLM API 密钥和模型配置

## 主要依赖

- **FastAPI**: Web 框架
- **SQLAlchemy + Alembic**: 数据库 ORM 和迁移
- **Fish Speech**: 语音克隆/TTS
- **Faster Whisper**: 快速语音转文字
- **yt-dlp**: 视频下载
- **LangChain**: LLM 集成
- **FFmpeg**: 媒体处理（需在项目根目录放置 ffmpeg.exe）

## 重要说明

- FFmpeg 二进制文件必须存在于项目根目录（`ffmpeg/` 文件夹）
- HuggingFace 模型缓存在 `D:/hf-model/` (Windows)
- 日志写入 `static/loginfo/`，按天自动滚动
- 每次启动 API 时会清空上传目录（`static/uploads/`）
- CORS 当前允许所有来源（仅开发环境）
