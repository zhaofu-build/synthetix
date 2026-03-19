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
├── repository/    # Repository 数据访问层
│   ├── base_repository.py    # 通用 CRUD 操作
│   ├── video_repository.py   # 视频素材数据访问
│   └── audio_repository.py   # 音频素材数据访问
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
│   ├── request.py         # 请求验证模型（使用常量）
│   ├── response.py        # 统一响应模型
│   └── entity/            # SQLAlchemy 实体定义
├── constants.py   # 常量定义（避免魔法数字）
├── exception/     # 异常处理
│   ├── exceptions.py      # 自定义异常类
│   └── exception_handlers.py  # 全局异常处理器
└── util/          # 工具类 (FFmpeg、文件操作等)
    ├── pagination.py      # 分页工具
    ├── task_manager.py    # 异步任务管理
    └── ...
```

### 关键设计模式

- **Repository 模式**: 数据访问层通过 Repository 类抽象，提供统一的 CRUD 接口
- **依赖注入**: 数据库会话通过 `get_db()` 依赖注入
- **关注点分离**: 路由在 `api/`，业务逻辑在 `service/`，数据访问在 `repository/`
- **静态文件**: 从 `static/` 目录提供（上传文件、日志、素材等）
- **自动初始化**: API 启动时自动运行 Alembic 数据库迁移
- **统一响应格式**: 使用 `APIResponse` 和 `success_response()`/`error_response()`

### Repository 层使用示例

```python
from src.repository import VideoRepository
from src.db.session import get_db

# 在 API 中使用
@router.get("/videos/{video_id}")
def get_video(video_id: int, db: Session = Depends(get_db)):
    repo = VideoRepository(db)
    video = repo.get_by_id(video_id)
    if not video:
        return error_response(error="NotFound", message="视频不存在", code=404)
    return success_response(data=repo.to_dict(video), message="获取成功")
```

### 数据库

- **类型**: SQLite (`src/db/we_library.db`)
- **ORM**: SQLAlchemy
- **迁移**: Alembic（启动时自动应用）
- **创建新迁移**: 修改 `src/model/entity/` 中的模型，然后执行 `alembic revision --autogenerate -m "描述"`

### 前端

- 已构建的前端文件位于 `dist/` 目录
- SPA 使用 history 模式路由（404 会回退到 index.html）

## 配置

### 环境变量 (.env)

创建 `.env` 文件配置环境变量：

```env
LLM_MODEL=deepseek
MODEL_NAME=deepseek-chat
LLM_KEY=your_llm_api_key_here
VIDEO_API_KEYS=your_video_api_key_here
CORS_ORIGINS=http://localhost:9528,http://127.0.0.1:9528
PROXY=http://127.0.0.1:7890  # 可选代理配置
```

### 配置文件

所有配置位于 `config.py`：
- `api_host` (9527)、`web_host` (9528): 服务端口
- `MODEL_CACHE_DIR`: HuggingFace 模型缓存位置
- `UPLOAD_DIR`、`source_*_dir`: 静态文件目录
- LLM API 密钥和模型配置

### 常量定义

所有常量定义在 `src/constants.py`：
- `FileSize`: 文件大小限制
- `Pagination`: 分页配置
- `VideoProcessing`: 视频处理常量
- `TTSConfig`: TTS 配置
- `Subtitle`: 字幕配置

## 测试

```bash
# 运行所有单元测试
pytest tests/unit/ -v

# 运行测试并生成覆盖率报告
pytest tests/unit/ --cov=src --cov-report=html

# 运行特定测试文件
pytest tests/unit/test_request.py -v
```

## 主要依赖

- **FastAPI**: Web 框架
- **SQLAlchemy + Alembic**: 数据库 ORM 和迁移
- **Pydantic v2**: 请求/响应验证
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
- CORS 配置通过 `CORS_ORIGINS` 环境变量控制
- 使用 Repository 层进行数据访问，避免在 API 层直接操作数据库
