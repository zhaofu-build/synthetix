# Synthetix

AI 视频剪辑平台，通过 AI 能力简化视频创作流程。

## 功能特性

### AI 对话剪辑
- **对话式剪辑** — 自然语言描述需求，Agent 自动调用工具完成剪辑
- **SSE 流式响应** — 思考过程、工具执行、结果逐步实时展示
- **深度研究模式** — 多阶段分析素材→规划方案→执行操作，处理复杂剪辑需求
- **73 个内置工具** — 视频剪切、合并、字幕、特效、音频处理、AI 分析等

### 编辑器
- **统一编辑器** — 三栏布局：工作区（剪辑方案/音频）| AI 对话 | 素材库 + 预览
- **项目管理** — 创建/切换/保存/导出项目，自动防抖保存
- **智能剪辑方案** — AI 根据文案和素材自动生成剪辑方案，应用到时间线
- **视频渲染** — FFmpeg 本地渲染，支持多输出

### AI 能力（通过 core-nexus-ai）
- **LLM** — 对话推理、意图理解、方案规划
- **TTS** — 语音合成、音色克隆
- **ASR** — 语音识别、视频转录
- **VL** — 视频理解、内容分析
- **音乐生成** — 文本生成背景音乐

### 素材与处理
- **素材管理** — 上传/下载/搜索素材，AI 自动分析生成描述
- **音视频处理** — 格式转换、字幕提取翻译、伴奏分离、批量压缩
- **BGM 管理** — 曲库管理、AI 选曲、AI 生成音乐
- **视频下载** — 支持上千个平台的视频一键下载（yt-dlp）

### 扩展性
- **扩展/插件** — 自定义扩展注入工具和系统提示词
- **MCP 协议** — 动态接入外部工具服务器
- **技能系统** — YAML 定义可复用技能
- **知识库** — 项目级 BM25 搜索，记录分析结果和备注
- **浏览器自动化** — CDP 协议控制浏览器搜索素材

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python 3.11, FastAPI, SQLAlchemy, Alembic, FFmpeg |
| 前端 | Vue 3, Vite, Pinia, Element Plus, Vue Router, vue-i18n |
| AI 服务 | core-nexus-ai（LLM, TTS, ASR, VL, 音乐生成） |
| 数据库 | SQLite |
| 部署 | Docker, docker-compose |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd synthetix-vue && npm install
```

### 2. 安装 FFmpeg

从 [FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases) 下载，将 `ffmpeg.exe` 和 `ffprobe.exe` 放入项目根目录的 `ffmpeg/` 文件夹。

### 3. 配置

复制 `.env.example` 为 `.env`，填入配置：

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=http://localhost:9528
```

可选配置：

```env
FAST_MODEL=                 # 快速模型（短文本/简单查询）
SLOW_MODEL=                 # 主模型（复杂任务，默认）
FAST_MODEL_THRESHOLD=100    # 快模型消息长度阈值
CHROME_CDP_URL=             # CDP 浏览器地址（浏览器自动化）
```

### 4. 初始化数据库

```bash
alembic upgrade head
```

### 5. 启动

```bash
# 构建前端 + 启动后端（单端口 9527，自动提供前端）
python main.py

# 或分别启动：
# 后端：python main.py
# 前端开发模式（热更新，端口 9528）：cd synthetix-vue && npm run dev
```

- Web 界面 + API 文档：http://127.0.0.1:9527
- Swagger UI：http://127.0.0.1:9527/docs
- 健康检查：http://127.0.0.1:9527/health
- 前端开发模式：http://127.0.0.1:9528

## Docker 部署

```bash
docker-compose up --build
```

端口 `9527`，挂载 `./src/db`（数据库）和 `./static`（素材文件）。

## 项目结构

```
src/
├── agent/                        # Agent 系统
│   ├── react_agent.py            #   ReAct Agent（TAOR 循环 + SSE 流式）
│   ├── tool_registry.py          #   73 个工具注册（Pydantic 校验 + Hook + 权限）
│   ├── session_manager.py        #   会话管理（内存 + DB 双写）
│   ├── mcp_client.py             #   MCP 协议客户端
│   ├── extension_loader.py       #   扩展/插件加载
│   ├── skill_loader.py           #   YAML 技能加载
│   ├── project_memory.py         #   项目级偏好记忆
│   ├── knowledge_base.py         #   BM25 知识库
│   └── multi_agent.py            #   多 Agent 协作（Plan→Execute→Review）
├── domain/entities/              # SQLAlchemy 数据模型
├── application/services/         # 业务逻辑（视频/音频处理、LLM、FFmpeg、渲染）
├── interfaces/api/               # FastAPI 路由（11 个模块）
├── shared/                       # 公共模型、工具类、core-nexus 客户端、CDP 浏览器
└── infrastructure/               # 数据库会话、Repository 层

synthetix-vue/src/
├── api/modules/                  # 后端 API 调用模块
├── store/modules/                # Pinia 状态管理
├── components/editor/            # 统一编辑器组件
├── locales/                      # 国际化（zh-CN, en-US）
├── layouts/                      # 布局
└── utils/                        # Markdown 渲染、API 封装

extensions/                       # 扩展/插件（示例：字幕风格预设）
skills/                           # YAML 技能定义
config/                           # 分层配置（default.json + settings.json）
```

## 开发命令

```bash
# 数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head

# 前端
cd synthetix-vue
npm run dev          # 开发服务器（端口 9528）
npm run build        # 生产构建
npm run lint         # 代码检查
npm run format       # 代码格式化

# 测试
pytest tests/unit/ -v
```

## API 概览

| 路径前缀 | 模块 | 说明 |
|----------|------|------|
| `/api/agent` | agent_api | AI 对话、流式响应、工具执行 |
| `/api/projects` | project_api | 项目 CRUD、时间线、方案、渲染 |
| `/api/videos` | video_api | 视频管理、处理、转录 |
| `/api/audios` | svc_api | 音色、TTS、音频分离/合并 |
| `/api/nexus` | core_nexus_api | AI 服务代理（LLM/TTS/ASR/VL/音乐） |
| `/api/tools` | tool_api | 上传、配置管理、日志 |
| `/api/tasks` | task_api | 任务中心 |
| `/api/mcp` | mcp_api | MCP Server 管理 |
| `/api/extensions` | extension_api | 扩展管理 |
| `/api/ai` | llm_clip_api | 关键词素材、转场 |
| `/ws` | ws_api | WebSocket（对话/渲染/通知） |

## License

Apache License 2.0
