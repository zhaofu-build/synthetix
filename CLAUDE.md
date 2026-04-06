# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Synthetix 是一个 AI 视频剪辑平台，提供两种剪辑模式：
1. **对话式 AI 剪辑** - 通过自然语言对话完成视频剪辑（Agent 模式）
2. **强控制性剪辑（工作流）** - 分步流程，用户精确控制每一步

后端通过 **core-nexus-ai** 统一推理框架调用 LLM、TTS、ASR、VL 等 AI 服务。

## 运行应用

```bash
# 启动 API (端口 9527)
python run_api.py

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

## 架构

```
src/
├── agent/                    # 对话式剪辑 Agent
│   ├── video_agent.py        # 主 Agent（意图识别→槽位填充→方案确认→工具执行）
│   ├── tool_registry.py      # 装饰器 @registry.register() 注册工具
│   └── prompts.py            # 提示词模板
│
├── domain/entities/          # SQLAlchemy 实体
│   ├── video_source.py       # 视频素材
│   ├── audio_source.py       # 音频素材（音色）
│   ├── video_project.py      # 视频项目 + ClipPlanItem
│   └── bgm_item.py           # BGM 素材
│
├── application/services/     # 业务服务
│   ├── video_service.py, audio_service.py   # 视频/音频处理
│   ├── clip_planner.py       # AI 剪辑方案规划
│   ├── render_service.py     # 视频渲染（FFmpeg）
│   ├── llm_adapter.py        # LLM 调用封装
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
│   ├── models/response.py    # success_response(to_camel=True) 自动转换
│   ├── models/timeline.py    # Timeline/ClipPlan 数据结构
│   └── utils/core_nexus_client.py  # core-nexus-ai 统一客户端
│
└── infrastructure/
    ├── db/                   # 数据库会话、Alembic
    └── repositories/         # Repository 数据访问层

synthetix-vue/                # 前端 Vue 3 + Vite + Pinia + Element Plus
├── src/api/
│   ├── request.js            # axios 实例（自动提取 data.data）
│   ├── utils/request.js      # fetch 封装（assetUrl, API_HOST）
│   └── modules/              # API 模块（video, audio, ai, project）
├── src/store/modules/
│   ├── system.js             # 主题、系统配置
│   └── project.js            # 项目 CRUD、防抖自动保存
├── src/components/
│   ├── ProjectList.vue       # 项目管理（/projects）
│   ├── VideoStitching.vue    # 工作流剪辑（/video-stitching）
│   ├── AIClip.vue            # 对话式剪辑（/ai-clip）
│   └── ...
└── src/components/config/api.js  # API 端点常量 + API_HOST
```

## 核心约定

### 命名转换
后端 snake_case → `success_response(to_camel=True)` 自动转 camelCase → 前端使用 camelCase。
前端 `debounceSave` 发送 snake_case key（`material_ids`, `target_duration` 等），后端 Pydantic 模型匹配 snake_case。

### 路由顺序
FastAPI 静态路由必须在动态路由（`/{id}`）之前定义，否则 `"bgm"` 等会被当作 `project_id`。

### 项目中心化
两种剪辑模式都基于项目：
- 进入页面先弹命名 dialog → 创建项目 → 后续操作自动保存到项目
- 从项目列表点"打开" → 加载已有项目回显
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

## Core-Nexus-AI 集成

所有 AI 推理通过 `CoreNexusClient` 调用：

| 功能 | 方法 |
|------|------|
| LLM 生成 | `client.llm_generate()` |
| LLM 流式 | `client.llm_generate_stream()` |
| TTS 合成 | `client.tts_generate()` |
| ASR 识别 | `client.asr_transcribe()` |
| VL 理解 | `client.vl_generate()` |
| 音乐生成 | `client.text_to_music()` |

## 对话式 Agent 工具注册

```python
# src/agent/tool_registry.py
@registry.register()
def my_tool(params):
    """工具描述"""
    ...
```

意图类型：cut_video, merge_videos, add_subtitle, add_audio, change_speed, smart_clip, analyze_video, generate_tts, list_videos, search_material

## 配置 (.env)

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=http://localhost:9528
API_PORT=9527
```

## 测试

```bash
pytest tests/unit/ -v                           # 运行单元测试
pytest tests/unit/test_xxx.py -v                # 运行单个测试
pytest tests/unit/ --cov=src --cov-report=html  # 覆盖率报告
```

## 其他约定

- **数据库**：SQLite (`src/db/synthetix.db`)，Alembic `render_as_batch=True` 兼容 SQLite ALTER TABLE
- **FFmpeg**：二进制文件在 `ffmpeg/` 文件夹
- **静态文件**：后端挂载 `/static` 目录，前端通过 `assetUrl(path)` 构建完整 URL
- **el-tag type**：合法值为 `success/warning/danger/info/primary`，不能传空字符串 `''`
- **ErrorBoundary**：`MainLayout.vue` 用 `ErrorBoundary.vue` 包裹 `router-view`
