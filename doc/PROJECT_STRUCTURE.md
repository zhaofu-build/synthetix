# 项目目录结构说明

## DDD 架构设计

项目采用领域驱动设计（DDD）的分层架构，结构如下：

```
src/
├── domain/                      # 领域层 - 核心业务逻辑
│   ├── entities/                # 领域实体
│   │   ├── __init__.py
│   │   ├── base.py              # 实体基类
│   │   ├── video_source.py      # 视频素材实体
│   │   └── audio_source.py      # 音频素材实体
│   └── repositories/            # 仓储接口（定义）
│       ├── __init__.py
│       └── interfaces.py
│
├── application/                 # 应用层 - 用例/服务
│   └── services/                # 应用服务
│       ├── __init__.py
│       ├── video_service.py     # 视频服务
│       ├── audio_service.py     # 音频服务
│       └── creative_service.py  # 创意内容服务
│
├── infrastructure/              # 基础设施层 - 技术实现
│   ├── db/                      # 数据库
│   │   ├── __init__.py
│   │   ├── session.py           # 会话管理
│   │   └── alembic_manager.py   # 迁移管理
│   ├── repositories/            # 仓储实现
│   │   ├── __init__.py
│   │   ├── base_repository.py
│   │   ├── video_repository.py
│   │   └── audio_repository.py
│   └── external/                # 外部服务
│       ├── __init__.py
│       ├── ffmpeg_service.py    # FFmpeg 封装
│       ├── whisper_service.py   # Whisper 封装
│       ├── langchain_service.py # LangChain 封装
│       ├── translation_service.py
│       └── video_downloader.py
│
├── interfaces/                  # 接口层 - API 控制器
│   └── api/                     # RESTful API
│       ├── __init__.py
│       ├── video_api.py         # 视频 API (/api/videos)
│       ├── audio_api.py         # 音频 API (/api/audios)
│       ├── tool_api.py          # 工具 API (/api/tools)
│       └── ai_api.py            # AI API (/api/ai)
│
└── shared/                      # 共享层 - 通用组件
    ├── __init__.py
    ├── constants.py             # 常量定义
    ├── models/                  # DTO 模型
    │   ├── __init__.py
    │   ├── request.py           # 请求模型
    │   ├── response.py          # 响应模型
    │   └── result.py            # 结果模型
    ├── utils/                   # 工具函数
    │   ├── __init__.py
    │   ├── file_util.py
    │   ├── time_util.py
    │   └── ...
    └── exceptions/              # 异常处理
        ├── __init__.py
        ├── exceptions.py
        └── exception_handlers.py
```

## 分层职责

| 层级 | 职责 | 依赖 |
|------|------|------|
| **Domain** | 核心业务概念、实体定义、仓储接口 | 无外部依赖 |
| **Application** | 用例编排、业务流程、服务协调 | Domain |
| **Infrastructure** | 数据库、外部服务、技术实现 | Domain |
| **Interfaces** | HTTP API、路由、请求响应处理 | Application |
| **Shared** | 通用工具、常量、DTO 模型 | 无外部依赖 |

## 导入路径映射

| 旧路径 | 新路径 |
|--------|--------|
| `src.model.entity.*` | `src.domain.entities.*` |
| `src.model.base.Base` | `src.domain.entities.base.Base` |
| `src.repository.*` | `src.infrastructure.repositories.*` |
| `src.service.*` | `src.application.services.*` |
| `src.api.*` | `src.interfaces.api.*` |
| `src.util.*` | `src.shared.utils.*` |
| `src.exception.*` | `src.shared.exceptions.*` |
| `src.constants` | `src.shared.constants` |
| `src.db.*` | `src.infrastructure.db.*` |

## 向后兼容

旧代码可以通过以下方式继续工作：

```python
# 旧代码（仍然可用）
from src.model.entity import VideoSource
from src.repository import VideoRepository
from src.service import VideoService

# 新代码（推荐）
from src.domain.entities import VideoSource
from src.infrastructure.repositories import VideoRepository
from src.application.services import VideoService
```

## 入口文件

- `run_api.py` - API 服务入口（端口 9527）
- `run_web.py` - Web UI 入口（端口 9528）

## 数据库迁移

```bash
# 创建新迁移
alembic revision --autogenerate -m "描述"

# 应用迁移
alembic upgrade head
```

## 测试目录

```
tests/
├── unit/              # 单元测试
│   ├── services/
│   └── repositories/
├── integration/       # 集成测试
│   └── api/
└── conftest.py        # pytest 配置
```
