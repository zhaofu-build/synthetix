# Super Agent Party (超级智能体派对) 项目详细分析文档

> 版本: v0.4.0 | 许可证: AGPL-3.0 | 作者: Heshengtao

---

## 一、项目概述

**Super Agent Party** 是一款功能极其丰富的 AI 桌面伴侣应用。它集成了 3D 虚拟角色（VRM 模型）、多模型智能对话、知识库 RAG、电脑控制、浏览器自动化、即时通讯机器人、直播机器人、任务中心、扩展系统等众多功能于一体，定位为"轻松链接一切"的全能 AI 桌面助手。

---

## 二、整体架构

```
┌─────────────────────────────────────────────────┐
│              Electron 桌面壳 (main.js)           │
│  ┌──────────────┐  ┌───────────────────────────┐ │
│  │  BrowserWindow│  │  VRM Window (Three.js)    │ │
│  │  (Vue.js SPA) │  │  VMC/OSC 协议收发         │ │
│  └──────┬───────┘  └───────────┬───────────────┘ │
│         │ WebSocket / HTTP      │                 │
│  ┌──────▼───────────────────────▼───────────────┐ │
│  │          Python FastAPI 后端 (server.py)       │ │
│  │  ┌──────────┐ ┌─────────┐ ┌───────────────┐  │ │
│  │  │ LLM 调用  │ │ 工具系统 │ │ MCP/A2A 客户端│  │ │
│  │  └──────────┘ └─────────┘ └───────────────┘  │ │
│  │  ┌──────────┐ ┌─────────┐ ┌───────────────┐  │ │
│  │  │ IM 机器人 │ │ 直播系统 │ │ 任务/调度中心 │  │ │
│  │  └──────────┘ └─────────┘ └───────────────┘  │ │
│  └───────────────────────────────────────────────┘ │
│         │ IPC / Child Process                      │
│  ┌──────▼───────────────────────────────────────┐ │
│  │  Node.js Runner (扩展/插件运行时)              │ │
│  └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────┘
```

**部署方式**:
- **桌面端**: Electron 包装 Python 后端，跨平台 (Windows / macOS / Linux)
- **Docker**: 纯 Python FastAPI 后端 + Nginx 网关，浏览器访问
- **整合包**: 免安装源码版本，一键启动

---

## 三、技术栈

### 3.1 桌面客户端 (Electron)

| 技术 | 版本/说明 | 用途 |
|------|-----------|------|
| Electron | ^39.2.6 | 桌面应用容器 |
| electron-builder | ^24.9.1 | 多平台打包 (NSIS/DMG/AppImage/deb) |
| electron-updater | ^6.6.2 | 自动更新 |
| @electron/remote | ^2.1.3 | 主进程/渲染进程通信 |
| chokidar | ^5.0.0 | 文件系统监听 |
| osc (node-osc) | ^2.4.5 | VMC 协议 UDP 收发 (骨骼/表情同步) |
| electron-dl | 3.5.0 | 文件下载管理 |

### 3.2 前端 (浏览器渲染层)

| 技术 | 用途 |
|------|------|
| **Vue.js 3** (CDN 模式) | 响应式 UI 框架，全局状态管理 |
| **Element Plus** | UI 组件库 (对话框、表单、菜单等) |
| **Three.js** + @pixiv/three-vrm | VRM 3D 模型渲染 |
| **Markdown-it** + 插件 | Markdown 渲染 (footnote/task-list/container) |
| **Mermaid** | 流程图/时序图渲染 |
| **KaTeX** (tex-svg) | 数学公式渲染 |
| **highlight.js** | 代码高亮 |
| **html2canvas** | 网页截图 |
| **QRCode.js** | 二维码生成 |
| **ExcelJS** | 前端 Excel 处理 |
| **ONNX Runtime Web** | 浏览器端 ML 推理 |
| **Silero VAD** | 语音活动检测 (浏览器端) |

### 3.3 后端 (Python)

| 技术 | 版本 | 用途 |
|------|------|------|
| **FastAPI** | >=0.115.12 | 异步 Web 框架 |
| **Uvicorn** | >=0.34.2 | ASGI 服务器 |
| **OpenAI SDK** | >=1.76.0 | LLM API 调用 |
| **httpx** | >=0.28.1 | 异步 HTTP 客户端 (连接池) |
| **LangChain** (community/openai/ollama) | >=0.3.x | RAG/Embedding/Retriever |
| **FAISS** (faiss-cpu) | >=1.10.0 | 向量相似度搜索 |
| **rank-bm25** | >=0.2.2 | BM25 关键词检索 |
| **MCP SDK** | >=1.6.0 | Model Context Protocol 客户端 |
| **fastapi-mcp** | >=0.3.4 | FastAPI 自动暴露 MCP 接口 |
| **python-a2a** | >=0.5.6 | Agent-to-Agent 协议 |
| **Mem0** | 1.0.0 | 长期记忆管理 |
| **E2B Code Interpreter** | >=1.5.0 | 沙箱代码执行 |
| **Sherpa-ONNX** | >=1.12.19 | 本地语音识别 (ASR) |
| **Edge-TTS** | >=7.0.2 | 微软 TTS |
| **ElevenLabs** | >=2.41.0 | 高质量 TTS |
| **tetos** | >=0.4.2 | 多引擎 TTS 聚合 |
| **PyAutoGUI** | >=0.9.54 | 鼠标键盘控制 |
| **pyttsx3** | >=2.99 | 本地 TTS |
| **transformers** | >=4.57.3 | HuggingFace 模型推理 |
| **litellm** | >=1.83.0 | 多 LLM 路由 |
| **Pillow** | - | 图像处理/截图标注 |
| **aiosqlite** | >=0.21.0 | 异步 SQLite |
| **BeautifulSoup4** | - | HTML 解析 |
| **PyPDF2/python-docx/openpyxl/python-pptx** | - | 文档解析 |

### 3.4 即时通讯 SDK

| SDK | 用途 |
|-----|------|
| **qq-botpy** | QQ 机器人 |
| **wechatbot-sdk** | 微信机器人 |
| **lark-oapi** | 飞书机器人 |
| **dingtalk-stream** | 钉钉机器人 |
| **discord.py** | Discord 机器人 |
| **slack-sdk** | Slack 机器人 |
| **python-telegram-bot** (内置实现) | Telegram 机器人 |
| **wecom-aibot-python-sdk** | 企业微信机器人 |

### 3.5 搜索与爬虫

| 引擎 | 说明 |
|------|------|
| **DuckDuckGo** | 免费搜索 |
| **Tavily** | AI 搜索 |
| **Bing** | 微软搜索 API |
| **Google** | Google Custom Search |
| **Brave** | Brave 搜索 |
| **Exa** | AI 语义搜索 |
| **SearXNG** | 自托管元搜索 |
| **Serper** | Google 搜索 API |
| **BochaAI** | AI 搜索 |
| **Jina** | 网页爬虫 |
| **Crawl4AI** | AI 爬虫 |
| **Firecrawl** | 网页抓取 |
| **Wikipedia API** | 维基百科 |
| **arxiv** | 学术论文 |

---

## 四、核心文件结构

```
super-agent-party/
├── main.js                    # Electron 主进程 (2102行) - 窗口管理、VMC、截图
├── server.py                  # FastAPI 后端主文件 (10685行) - API路由、LLM调度、流处理
├── start.js                   # Electron 启动入口
├── package.json               # Node.js 依赖与打包配置
├── pyproject.toml             # Python 依赖 (uv 管理)
├── Dockerfile                 # Docker 镜像构建
├── docker-compose.yml         # Docker Compose (后端 + Nginx 网关)
├── config/
│   ├── settings_template.json # 默认配置模板 (~300项配置)
│   └── locales.json           # 国际化翻译
├── py/                        # Python 后端模块 (18696行)
│   ├── agent.py               # 项目级工具权限管理
│   ├── agent_tool.py          # Agent 工具调用 (多Agent间通信)
│   ├── a2a_tool.py            # A2A 协议工具
│   ├── affection_system.py    # 好感度系统
│   ├── autoBehavior.py        # 自动行为触发器
│   ├── behavior_engine.py     # 通用行为引擎 (定时/空闲/周期)
│   ├── cdp_tool.py            # Chrome DevTools Protocol 浏览器控制
│   ├── cli_tool.py            # CLI 开发环境工具集 (2386行)
│   ├── code_interpreter.py    # E2B/本地代码解释器
│   ├── comfyui_tool.py        # ComfyUI 图片生成
│   ├── computer_use_tool.py   # 电脑鼠标键盘控制
│   ├── custom_http.py         # 自定义 HTTP 工具
│   ├── dify_openai.py         # Dify 平台适配 (OpenAI 兼容)
│   ├── ClaudeAsOpenAI.py      # Claude API 转 OpenAI 格式
│   ├── discord_bot_manager.py # Discord 机器人管理
│   ├── dingtalk_bot_manager.py# 钉钉机器人管理
│   ├── docker_api.py          # Docker 沙箱 API
│   ├── ebd_api.py             # Embedding API
│   ├── ebd_model_manager.py   # MiniLM 模型下载管理
│   ├── extensions.py          # 扩展系统 (安装/卸载/运行)
│   ├── feishu_bot_manager.py  # 飞书机器人管理 (1398行)
│   ├── get_setting.py         # 全局配置/路径/数据库管理
│   ├── image_host.py          # 图床上传
│   ├── know_base.py           # 知识库 RAG (FAISS + BM25)
│   ├── live_router.py         # 直播弹幕路由 (B站/YouTube/Twitch)
│   ├── llm_tool.py            # LLM 工具 (图片处理等)
│   ├── load_files.py          # 文件加载/解析 (752行, 支持30+格式)
│   ├── mcp_clients.py         # MCP 客户端 (stdio/SSE/WS/StreamableHTTP)
│   ├── minilm_router.py       # MiniLM Embedding 服务路由
│   ├── node_runner.py         # Node.js 扩展运行时管理
│   ├── overlay_router.py      # 弹幕/字幕覆盖层路由
│   ├── pollinations.py        # Pollinations AI 图片生成
│   ├── qq_bot_manager.py      # QQ 机器人管理 (879行)
│   ├── random_topic.py        # 随机话题生成
│   ├── scheduler.py           # 任务调度器 (定时/周期任务)
│   ├── sherpa_asr.py          # Sherpa-ONNX 语音识别
│   ├── sherpa_model_manager.py# Sherpa 模型下载管理
│   ├── skills.py              # Skills 技能系统 (安装/同步)
│   ├── slack_bot_manager.py   # Slack 机器人管理
│   ├── sub_agent.py           # 子智能体执行器
│   ├── task_center.py         # 任务中心 (CRUD + 状态机)
│   ├── task_tools.py          # 任务工具 (创建/查询/取消/完成)
│   ├── telegram_bot_manager.py# Telegram 机器人管理
│   ├── telegram_client.py     # Telegram 客户端实现
│   ├── twitch_service.py      # Twitch 直播服务
│   ├── utility_tools.py       # 通用工具 (天气/维基/ArXiv/时间)
│   ├── web_search.py          # 搜索引擎聚合 (1059行)
│   ├── wechat_bot_manager.py  # 微信机器人管理
│   ├── wecom_bot_manager.py   # 企业微信机器人管理
│   └── ytdm.py                # YouTube 弹幕客户端
├── static/                    # 前端静态资源
│   ├── index.html             # 主页面 (16625行, 含 Vue 模板)
│   ├── chat.html              # 独立聊天页面
│   ├── vrm.html               # VRM 3D 渲染页面
│   ├── skeleton.html          # 启动骨架屏
│   ├── shotOverlay.html       # 截图覆盖层
│   ├── danmaku_overlay.html   # 弹幕覆盖层
│   ├── subtitle_overlay.html  # 字幕覆盖层
│   ├── js/
│   │   ├── vue_data.js        # Vue 响应式数据定义 (85008字节)
│   │   ├── vue_methods.js     # Vue 方法集 (592374字节)
│   │   ├── renderer.js        # 渲染逻辑
│   │   ├── vrm.js             # VRM 模型渲染 (Three.js)
│   │   ├── preload.js         # Electron preload 脚本
│   │   └── locales/           # 国际化文件
│   ├── css/styles.css         # 主样式 (298KB)
│   ├── libs/                  # 第三方 JS 库
│   └── source/                # 图标/资源文件
├── vrm/                       # 默认 VRM 模型和动画
│   ├── Alice.vrm / Bob.vrm    # 内置 3D 角色模型
│   └── animations/            # VRMA 动画文件
├── skills/                    # 内置 Skills
│   ├── find-skills/           # 技能搜索
│   ├── officeCLI/             # 办公 CLI
│   └── skill-creator/         # 技能创建器
└── doc/                       # 文档图片
```

---

## 五、功能模块详解

### 5.1 VRM 3D 桌面宠物

**实现文件**: `main.js` (VMC部分), `static/vrm.html`, `static/js/vrm.js`, `vrm/` 目录

**技术实现**:
- 使用 **Three.js** + `@pixiv/three-vrm` 加载 VRM 1.0/0.x 格式的 3D 人物模型
- Electron 创建独立 BrowserWindow 渲染 VRM，通过 IPC 与主窗口通信
- **VMC (Virtual Motion Capture) 协议**: 通过 `osc` 库建立 UDP 收发端口
  - 接收 `/VMC/Ext/Bone/Pos` 骨骼位置/旋转数据
  - 接收 `/VMC/Ext/Blend/Val` 表情混合形状数据
  - 可将 VRM 的骨骼/表情数据转发给其他 VMC 兼容软件
- **VRMA 动画**: 内置 Alice.vrm 和 Bob.vrm 模型，支持上传自定义模型和动画
- **3D 场景**: 支持 Gauss Splatting 360度全景场景
- 支持 **Live2D** 扩展 (通过 sap-live2d 插件)

### 5.2 多模型智能对话

**实现文件**: `server.py` (`/v1/chat/completions`), `static/index.html`, `static/js/vue_methods.js`

**架构设计 - 快慢双脑**:

```
用户消息 ──→ 条件判断器 ──→ 快速模型 (简单/短文本)
                         └→ 主模型 (复杂/长文本/含图片)
                             ├→ 推理模型 (reasoner, 思考链)
                             └→ 工具调用循环 (tool loop)
```

**具体实现**:
- **超级模型 (super-model)**: 虚拟模型名，路由到用户配置的主 LLM
- **快慢双脑**: `fast` 配置节，可设置条件触发 (文本长度/是否包含换行/是否包含文件)
- **多 Provider 支持**: OpenAI 兼容 API、Dify 平台、Claude API (通过 ClaudeAsOpenAI 适配器)
- **流式响应**: SSE (Server-Sent Events) 实时流式输出
- **推理模式**: 支持 `reasoning_content` 字段的思考链输出
- **深度研究 (Deep Research)**: 多阶段搜索研究流程 (DRS_STAGE 机制)
  - Stage 1: 初步搜索与任务分解
  - Stage 2: 深入搜索缺失信息
  - Stage 3: 综合回答
- **多轮工具调用**: 自动循环调用工具直到任务完成
- **Agent 系统**: 支持创建多个独立 Agent，每个有自己的配置、系统提示、模型

### 5.3 知识库 RAG (检索增强生成)

**实现文件**: `py/know_base.py`, `py/ebd_model_manager.py`, `py/minilm_router.py`, `py/load_files.py`

**技术实现**:
- **文档解析**: 支持 30+ 种文件格式
  - 办公文档: doc, docx, ppt, pptx, xls, xlsx, pdf, rtf, odt, epub
  - 编程开发: js, ts, py, java, c, cpp, go, rs, vue, jsx, tsx 等
  - 数据配置: csv, tsv, txt, md, json, xml, yml, yaml, sql, sh
- **文本分割**: LangChain `RecursiveCharacterTextSplitter`
- **混合检索**: FAISS 向量搜索 + BM25 关键词检索，通过 `EnsembleRetriever` 融合
- **Embedding 模型**:
  - 远程: OpenAI 兼容 Embedding API
  - 本地: `paraphrase-multilingual-MiniLM-L12-v2` (ONNX 格式，支持 ModelScope/HuggingFace 下载)
- **Rerank**: 可选的重排序功能
- **知识库管理**: 创建/删除/状态查询，每个知识库独立索引

### 5.4 网络搜索

**实现文件**: `py/web_search.py` (1059行)

**支持的搜索引擎** (全部实现为 OpenAI Function Calling 工具):
| 引擎 | 工具名 | 说明 |
|------|--------|------|
| DuckDuckGo | `DDGsearch` | 免费搜索，无需 API Key |
| SearXNG | `searxng` | 自托管元搜索 |
| Tavily | `Tavily_search` | AI 搜索 |
| Bing | `Bing_search` | 微软搜索 API |
| Google | `Google_search` | Google Custom Search |
| Brave | `Brave_search` | Brave 搜索 |
| Exa | `Exa_search` | AI 语义搜索 |
| Serper | `Serper_search` | Google 搜索 API |
| BochaAI | `bochaai_search` | AI 搜索 |

**爬虫工具**:
| 爬虫 | 工具名 | 说明 |
|------|--------|------|
| Jina Reader | `jina_crawler` | AI 网页摘要 |
| Crawl4AI | `Crawl4Ai_search` | AI 爬虫 |
| Firecrawl | `firecrawl_search` | 网页抓取 |
| Simple Fetch | `simple_fetch` | 基础 HTTP 抓取 |
| Markdown | `markdown_new` | URL 转 Markdown |

**搜索时机**: 支持 `before_thinking` / `after_thinking` 配置

### 5.5 电脑控制 (Computer Use)

**实现文件**: `py/computer_use_tool.py` (575行), `server.py` (截图/网格绘制)

**控制能力**:
- **鼠标控制**: `mouse_move` / `mouse_click` / `mouse_double_click` / `mouse_drag` / `mouse_scroll` / `mouse_hold`
- **键盘控制**: `keyboard_press` / `keyboard_sequence` / `keyboard_hotkey` / `keyboard_hold`
- **剪贴板**: `copy_to_input_box`
- **截图**: `screenshot` - 使用 PIL 截取屏幕
- **网格系统**: 截图上自动绘制千分比坐标网格，LLM 通过坐标定位元素
- **视觉反馈**: 在截图上绘制操作轨迹 (点击位置、拖拽路径等)

**坐标映射**: 采用千分比坐标系统 (0-1000)，自动映射到实际屏幕像素，支持全屏或局部区域

**安全机制**: Docker/无头环境自动检测，禁用 GUI 操作并返回友好提示

### 5.6 浏览器自动化 (CDP)

**实现文件**: `py/cdp_tool.py` (559行)

**基于 Chrome DevTools Protocol 的浏览器控制工具**:

| 工具名 | 功能 |
|--------|------|
| `list_pages` | 列出所有浏览器标签页 |
| `new_page` | 新建标签页 |
| `close_page` | 关闭标签页 |
| `select_page` | 切换标签页 |
| `navigate_page` | 导航到 URL |
| `take_snapshot` | 获取页面 DOM 快照 (Accessibility Tree) |
| `click` | 点击元素 |
| `fill` | 填写输入框 |
| `fill_form` | 批量填写表单 |
| `hover` | 悬停元素 |
| `press_key` | 按键 |
| `drag` | 拖拽元素 |
| `evaluate_script` | 执行 JavaScript |
| `take_screenshot` | 截取页面截图 |
| `handle_dialog` | 处理对话框 |

**连接方式**: 通过 WebSocket 连接到 Chrome 的 CDP 端口 (默认 9222)

### 5.7 代码解释器 (Code Interpreter)

**实现文件**: `py/code_interpreter.py` (91行)

**两种执行引擎**:
1. **E2B 沙箱**: 通过 E2B Code Interpreter API 在云端安全沙箱中执行代码
2. **本地执行**: 通过本地 HTTP 端点执行代码 (sandbox_url 配置)

**支持的代码操作**: Python 代码执行、文件上传/下载、图表生成

### 5.8 CLI 开发环境工具

**实现文件**: `py/cli_tool.py` (2386行, 项目最大的单一模块)

**完整开发环境工具集，分为 Docker 沙箱和本地两种模式**:

**Docker 沙箱工具**:
| 工具名 | 功能 |
|--------|------|
| `docker_sandbox` | 执行 Shell 命令 |
| `list_files_tool` | 列出文件目录 |
| `read_file_tool` | 读取文件内容 |
| `read_file_range_tool` | 读取文件指定行范围 |
| `tail_file_tool` | 读取文件末尾 |
| `search_files_tool` | 搜索文件内容 (grep) |
| `edit_file_tool` | 写入文件 |
| `edit_file_patch_tool` | 精确替换文件内容 (patch) |
| `glob_files_tool` | Glob 模式查找文件 |
| `todo_write_tool` | 任务管理 |
| `manage_processes_tool` | 进程管理 |
| `docker_manage_ports_tool` | 端口管理 |
| `read_skill_tool` | 读取技能文件 |

**本地工具**: 与 Docker 版本功能一一对应 (加 `_local` 后缀)，操作本地文件系统

**额外工具**: `local_net_tool` (本地网络请求)

**权限系统 (Human-in-the-Loop)**:
- **YOLO 模式**: 跳过所有权限检查
- **Auto-approve 模式**: 自动批准文件编辑，拦截终端命令
- **Default 模式**: 全部拦截，等待用户确认
- **Cowork 模式**: 协作模式
- **项目级白名单**: `.party/config.json` 记录用户"始终允许"的工具

### 5.9 任务中心

**实现文件**: `py/task_center.py` (258行), `py/task_tools.py` (338行), `py/sub_agent.py` (204行), `py/scheduler.py` (134行)

**任务类型**:
- **单次任务 (once)**: 立即执行
- **定时任务 (time)**: 指定时间执行，支持按星期重复
- **周期任务 (cycle)**: 每隔固定时长执行

**架构设计**:
```
用户/AI 创建任务 → TaskCenter (状态机: PENDING → RUNNING → COMPLETED/FAILED)
                         │
                    SubAgentExecutor (后台异步执行)
                         │  ┌── 迭代循环 ──┐
                         └→ │ 调用 LLM     │
                            │ 执行工具     │
                            │ 检查完成     │
                            └──────────────┘
                         │
                    AgentScheduler (30秒轮询，触发定时/周期任务)
```

**API 接口**:
- `GET /v1/tasks/list` - 列出所有任务
- `POST /v1/tasks/create` - 创建任务
- `POST /v1/tasks/cancel/{task_id}` - 取消任务
- `DELETE /v1/tasks/{task_id}` - 删除任务

**工具接口 (AI 可调用)**:
- `create_subtask` - 创建子任务
- `query_task_progress` - 查询进度
- `cancel_subtask` - 取消任务
- `finish_task` - 完成任务

### 5.10 MCP (Model Context Protocol) 集成

**实现文件**: `py/mcp_clients.py` (189行), `server.py` (MCP 管理接口)

**传输协议支持**:
- **stdio**: 本地进程通信 (通过 uv 命令启动 MCP Server)
- **SSE**: Server-Sent Events
- **WebSocket**: ws://
- **StreamableHTTP**: HTTP 流式传输

**生命周期管理**:
- 启动时并行初始化所有配置的 MCP Server (6秒超时)
- 失败自动标记 `server_error` 并禁用
- 运行时动态创建/删除 MCP 连接
- MCP 工具自动注入到 LLM 的 Function Calling 工具列表

**API 接口**:
- `POST /create_mcp` - 创建 MCP 连接
- `GET /mcp_status/{mcp_id}` - 查询 MCP 状态
- `DELETE /remove_mcp` - 删除 MCP

**FastAPI MCP**: 使用 `fastapi-mcp` 自动将 FastAPI 路由暴露为 MCP 工具

### 5.11 A2A (Agent-to-Agent) 协议

**实现文件**: `py/a2a_tool.py` (39行), `server.py` (A2A 管理接口)

**实现**:
- 基于 `python-a2a` 库的 Agent 间通信
- 支持 Agent 注册、发现和消息传递
- A2A 工具可被 LLM 调用来与其他 Agent 交互

### 5.12 即时通讯机器人

**支持的 8 个平台**:

| 平台 | 实现文件 | SDK | 管理接口 |
|------|----------|-----|----------|
| QQ | `py/qq_bot_manager.py` | qq-botpy | start/stop/status/reload |
| 微信 | `py/wechat_bot_manager.py` | wechatbot-sdk | start/stop/status/reload |
| 飞书 | `py/feishu_bot_manager.py` | lark-oapi | start/stop/status/reload |
| 钉钉 | `py/dingtalk_bot_manager.py` | dingtalk-stream | start/stop/status/reload |
| Discord | `py/discord_bot_manager.py` | discord.py | start/stop/status/reload |
| Slack | `py/slack_bot_manager.py` | slack-sdk | start/stop/status/reload |
| Telegram | `py/telegram_bot_manager.py` | 自研客户端 | start/stop/status/reload |
| 企业微信 | `py/wecom_bot_manager.py` | wecom-aibot-python-sdk | start/stop/status/reload |

**统一设计模式**:
- 每个 Bot Manager 都有 `start_bot()` / `stop_bot()` / `is_running` 生命周期管理
- 独立线程运行 Bot 事件循环，不阻塞 FastAPI 主线程
- 统一的配置模型 (LLM 模型、记忆轮数、分隔符、推理可见性等)
- 集成 **行为引擎** (BehaviorEngine)，支持定时/空闲/周期行为
- 支持消息分段发送 (按分隔符拆分长回复)
- 支持推理过程可见性配置
- 支持图片收发 (Base64 编码)

### 5.13 直播机器人

**实现文件**: `py/live_router.py` (546行), `py/ytdm.py` (132行), `py/twitch_service.py` (210行), `py/blivedm/`

**支持平台**:
- **Bilibili**: 通过 blivedm 库接收弹幕，支持开放平台和网页端两种模式
- **YouTube**: 通过 YouTube Data API v3 获取直播聊天消息
- **Twitch**: 通过 IRC 接收聊天消息

**架构**:
```
直播平台弹幕 → 各平台 Client → WebSocket (/ws/live/danmu) → 前端弹幕显示
                                    ↓
                               LLM 生成回复
                                    ↓
                               TTS 语音合成 (可选)
                                    ↓
                               弹幕覆盖层显示
```

**功能**:
- 实时弹幕接收与显示
- AI 自动回复弹幕
- 弹幕覆盖层 (透明窗口叠加在直播画面上)
- 字幕覆盖层 (显示 AI 语音的文字)
- 支持 360 度全景直播

### 5.14 语音识别 (ASR)

**实现文件**: `py/sherpa_asr.py` (93行), `py/sherpa_model_manager.py` (249行), `server.py` (/ws/asr, /asr)

**技术实现**:
- **引擎选择**: Sherpa-ONNX (本地) / OpenAI Whisper API (云端) / Web Speech API (浏览器) / FunASR (WebSocket)
- **默认模型**: `sherpa-onnx-sense-voice-zh-en-ja-ko-yue` (中日英韩粤五语种)
- **WebSpeech**: 前端浏览器原生语音识别
- **交互模式**: 自动检测 (VAD) / 按键触发 / 唤醒词
- **WebSocket**: `/ws/asr` 实时音频流传输
- **唤醒词**: 可配置唤醒词 (默认"小派") 和结束词

**VAD (语音活动检测)**:
- 前端: Silero VAD (ONNX Runtime Web 推理)
- 检测到语音结束后自动发送给 ASR

### 5.15 语音合成 (TTS)

**实现文件**: `server.py` (/ws/tts, /tts, /tts/tetos/list_voices, /system/voices)

**支持的 TTS 引擎**:
| 引擎 | 说明 |
|------|------|
| Edge-TTS | 微软免费 TTS，质量高 |
| OpenAI TTS | OpenAI 官方 TTS API |
| ElevenLabs | 高质量 TTS |
| pyttsx3 | 本地 TTS (离线) |
| tetos | 多引擎聚合 (支持多种语音) |
| GSV (Voice Clone) | 声音克隆 |

**实现细节**:
- **OmniTTS**: 统一 TTS 接口，所有回复自动合成语音
- **WebSocket**: `/ws/tts` 实时流式音频传输
- **VRM 口型同步**: `/ws/vrm` 将音频数据发送给 VRM 窗口进行口型同步
- **字幕同步**: `/ws/subtitles` 字幕覆盖层

### 5.16 长期记忆 (Memory)

**实现文件**: Mem0 集成 (`server.py`)

**实现**:
- 基于 **Mem0** 库的记忆管理
- 每次对话后自动提取关键信息并存储
- 后续对话自动检索相关记忆注入上下文
- 支持 `memory/{memory_id}` 的 CRUD 操作
- 可配置记忆轮数限制 (`memoryLimit`)
- 用户名配置，个性化记忆关联

### 5.17 好感度系统 (Affection System)

**实现文件**: `py/affection_system.py` (64行), `py/affection_api.py` (29行)

**实现**:
- AI 回复中嵌入 `<user=用户名 love=数值 familiarity=数值>` 格式的标签
- 系统自动从 AI 回复中正则提取好感度数据
- 数据持久化到 `affection_data.json`
- 支持自定义属性 (love, familiarity 等任意属性)

### 5.18 行为引擎 (Behavior Engine)

**实现文件**: `py/behavior_engine.py` (219行), `py/autoBehavior.py` (117行)

**触发类型**:
| 类型 | 说明 | 配置 |
|------|------|------|
| **定时 (time)** | 特定时间触发 | HH:mm:ss + 星期选择 |
| **空闲 (noInput)** | 用户无输入超时触发 | 延迟时间 (秒) |
| **周期 (cycle)** | 固定间隔循环触发 | 间隔时长 + 重复次数 |

**动作类型**:
- **提示词 (prompt)**: 向 LLM 发送指定提示词
- **随机 (random)**: 从预设事件列表中随机选择
- **话题 (topic)**: 从随机话题 API 获取话题

**平台适配**: 每条行为规则可指定生效平台 (chat/feishu/dingtalk/all)

### 5.19 文生图 (Text-to-Image)

**实现文件**: `py/pollinations.py` (224行), `py/comfyui_tool.py` (217行), `server.py`

**支持的引擎**:
| 引擎 | 工具名 | 说明 |
|------|--------|------|
| Pollinations | `pollinations_image` | 免费 AI 图片生成 (Flux 模型) |
| OpenAI DALL-E | `openai_image` | OpenAI 图片生成 |
| OpenAI 聊天图片 | `openai_chat_image` | 通过聊天 API 生成图片 |
| ComfyUI | `comfyui_tool_call` | 本地 ComfyUI 工作流调用 |

### 5.20 扩展系统 (Extensions)

**实现文件**: `py/extensions.py` (709行), `py/node_runner.py` (123行)

**架构**:
```
扩展 manifest.json → Node.js 运行时 → 独立进程 → Extension Proxy
                                              ↓
                                    独立窗口 / 侧边栏
```

**扩展模型**:
```json
{
  "id": "扩展ID",
  "name": "扩展名称",
  "description": "描述",
  "version": "1.0.0",
  "author": "作者",
  "systemPrompt": "扩展注入的系统提示词",
  "repository": "GitHub 仓库地址",
  "transparent": false,        // 透明窗口模式
  "width": 800, "height": 600, // 窗口尺寸
  "enableVrmWindowSize": false  // 跟随 VRM 窗口大小
}
```

**核心功能**:
- 从 GitHub 仓库一键安装/更新扩展
- 扩展独立窗口或侧边栏两种显示模式
- Node.js 运行时支持 (通过 `node_runner.py` 管理)
- Extension Proxy 路由 (`/extension_proxy`) 转发扩展请求
- 官方扩展市场: [super-agent-party.github.io](https://super-agent-party.github.io/plugins.html)

**已有扩展**:
| 名称 | 功能 |
|------|------|
| sap-example | 示例插件 |
| sap-example-with-node | 带 NodeJS 环境的示例 |
| sap-web-preview | 网页预览 |
| sap-story-adventure | AI 故事冒险 |
| sap-live2d | Live2D 前端插件 |
| sap-aieditor | AI 编辑器 |
| sap-aigalgame | AI Galgame |
| sap-tarot | AI 塔罗牌 |
| sap-ai-sheet | AI 表格 |

### 5.21 Skills 技能系统

**实现文件**: `py/skills.py` (696行)

**实现**:
- 技能以 YAML 定义，包含工具描述和执行逻辑
- 支持从 GitHub 仓库安装 (支持子目录)
- 全局技能目录: `~/.agents/skills`
- 技能文件自动注入到 LLM 上下文中作为可用工具
- 技能可被 AI 自动调用 (`read_skill_tool`)

**内置技能**:
- `find-skills` - 技能搜索
- `officeCLI` - 办公 CLI
- `skill-creator` - 技能创建器

### 5.22 多 Agent 系统

**实现文件**: `server.py` (Agent 路由), `py/agent_tool.py`

**实现**:
- 支持创建多个独立 Agent，每个有自己的:
  - 名称、系统提示词
  - 独立的 LLM 模型配置
  - 独立的记忆系统
  - 独立的工具集
- **Agent 工具调用**: `agent_tool_call` 允许一个 Agent 调用另一个 Agent
- **虚拟模型路由**: 通过 `/v1/chat/completions` 的 `model` 参数指定目标 Agent
- **API 接口**: `DELETE /remove_agent` 删除 Agent

### 5.23 开放 API

**实现文件**: `server.py`

**对外接口**:
- `GET /v1/models` - 获取可用模型列表 (OpenAI 兼容)
- `POST /v1/chat/completions` - 聊天补全 (OpenAI 兼容，operationId: `chat_with_agent_party`)
- `POST /v1/providers/models` - 获取指定 Provider 的模型列表
- `GET /v1/agents` - 获取 Agent 列表
- `POST /simple_chat` - 简单聊天 (无工具、无流式)

**兼容性**:
- 完全兼容 OpenAI Chat Completions API 格式
- 支持 `memory/{memory_id}/model` 格式指定特定记忆上下文
- FastAPI MCP 自动将路由暴露为 MCP 工具

### 5.24 代理与网络

**实现文件**: `server.py` (代理初始化), `py/get_setting.py`

**代理模式**:
- **系统代理 (system)**: 自动检测系统代理设置 (`trust_env=True`)
- **手动代理 (manual)**: 用户指定代理 URL
- **中国代理优化**: 自动注入 npm/pip 国内镜像源
  - npm: `https://registry.npmmirror.com/`
  - pip: `https://mirrors.aliyun.com/pypi/simple/`
- **SOCKS 防护**: 自动移除 SOCKS 代理环境变量，防止 httpx 崩溃

### 5.25 数据持久化

**实现文件**: `py/get_setting.py`

**存储结构**:
```
~/.Super-Agent-Party/          (Windows: %APPDATA%/Super-Agent-Party/)
├── settings.json               # 全局配置
├── super_agent_party.db        # SQLite 主数据库 (aiosqlite)
├── conversations.db            # 对话历史数据库
├── logs/                       # 日志文件
├── memory_cache/               # 记忆缓存
├── uploaded_files/             # 上传的文件
├── tool_temp/                  # 工具临时文件
├── agents/                     # Agent 配置
├── kb/                         # 知识库索引
├── ext/                        # 扩展安装目录
├── asr/                        # ASR 模型
├── ebd/                        # Embedding 模型
└── affection/                  # 好感度数据
```

### 5.26 国际化 (i18n)

**实现文件**: `config/locales.json`, `static/js/locales/`, `server.py` (`t()` 函数)

- 支持多语言界面
- 后端翻译函数 `t(text)` 根据当前语言设置返回翻译
- 前端通过 Vue 的 locale 机制切换语言

### 5.27 深度研究 (Deep Research)

**实现文件**: `server.py` (DRS_STAGE 机制)

**多阶段研究流程**:
1. **Stage 1 - 初始搜索**: 分解任务，执行搜索，判断完成度
2. **Stage 2 - 深入研究**: 针对缺失信息继续搜索
3. **Stage 3 - 综合回答**: 整合所有搜索结果，生成最终答案

**状态判断**: AI 自动评估研究状态 (`done` / `not_done` / `need_more_info` / `need_work` / `answer`)

---

## 六、WebSocket 端点

| 路径 | 功能 |
|------|------|
| `/ws` | 主 WebSocket - 前后端双向通信 (设置同步、消息推送) |
| `/ws/asr` | 语音识别 - 实时音频流 |
| `/ws/tts` | 语音合成 - 实时音频播放 |
| `/ws/vrm` | VRM 模型 - 口型同步数据 |
| `/ws/subtitles` | 字幕 - 字幕覆盖层数据 |
| `/ws/live/danmu` | 直播弹幕 - 实时弹幕推送 (通过 live_router) |

---

## 七、API 路由汇总

### 核心聊天
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/v1/chat/completions` | OpenAI 兼容聊天接口 |
| POST | `/simple_chat` | 简单聊天 (无工具) |
| GET | `/v1/models` | 模型列表 |
| POST | `/v1/providers/models` | Provider 模型列表 |
| GET | `/v1/agents` | Agent 列表 |

### 任务中心
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/v1/tasks/list` | 任务列表 |
| POST | `/v1/tasks/create` | 创建任务 |
| POST | `/v1/tasks/cancel/{id}` | 取消任务 |
| DELETE | `/v1/tasks/{id}` | 删除任务 |
| POST | `/execute_tool_manually` | 手动执行工具 (权限审批) |

### MCP / A2A
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/create_mcp` | 创建 MCP 连接 |
| GET | `/mcp_status/{id}` | MCP 状态 |
| DELETE | `/remove_mcp` | 删除 MCP |
| POST | `/a2a` | A2A 通信 |

### 文件管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/load_file` | 上传文件 |
| DELETE | `/delete_file` | 删除文件 |
| DELETE | `/delete_files` | 批量删除 |
| GET | `/get_file_content` | 获取文件内容 |
| GET | `/update_storage` | 获取存储信息 |

### 知识库
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/create_kb` | 创建知识库 |
| DELETE | `/remove_kb` | 删除知识库 |
| GET | `/kb_status/{id}` | 知识库状态 |

### TTS / ASR / 语音
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/tts` | 文本转语音 |
| POST | `/asr` | 语音识别 |
| GET | `/tts/status` | TTS 状态 |
| POST | `/tts/tetos/list_voices` | Tetos 语音列表 |
| GET | `/system/voices` | 系统语音列表 |

### VRM 模型管理
| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/upload_vrm_model` | 上传 VRM 模型 |
| GET | `/get_default_vrm_models` | 获取默认模型 |
| DELETE | `/delete_vrm_model/{name}` | 删除模型 |
| GET | `/get_default_vrma_motions` | 获取默认动画 |
| GET | `/vrm_config` | VRM 配置 |

### IM 机器人 (8平台 x 4接口)
| 方法 | 路径模式 | 说明 |
|------|----------|------|
| POST | `/start_{platform}_bot` | 启动机器人 |
| POST | `/stop_{platform}_bot` | 停止机器人 |
| GET | `/{platform}_bot_status` | 机器人状态 |
| POST | `/reload_{platform}_bot` | 重载机器人 |

平台: `qq` / `wechat` / `feishu` / `dingtalk` / `discord` / `slack` / `telegram` / `wecom`

### 其他
| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/cur_language` | 当前语言 |
| POST | `/api/update_proxy` | 更新代理设置 |
| GET | `/api/get_userfile` | 获取用户文件 |
| POST | `/sys/shutdown` | 系统关闭 |

---

## 八、配置系统

### 配置层级
```
config/settings_template.json   (默认模板)
         ↓
~/.Super-Agent-Party/settings.json  (用户配置，运行时内存覆盖)
         ↓
WebSocket 广播同步到前端
```

### 关键配置项

| 配置节 | 说明 |
|--------|------|
| `system_prompt` | 系统提示词 |
| `model` / `base_url` / `api_key` | 主模型配置 |
| `temperature` / `max_tokens` / `top_p` | 模型参数 |
| `modelProviders[]` | 多模型 Provider 列表 |
| `fast` | 快速模型配置 (触发模式/条件) |
| `reasoner` | 推理模型配置 |
| `vision` | 视觉模型配置 (图片理解) |
| `webSearch` | 搜索引擎配置 (10种引擎) |
| `tools` | 工具开关 (时间/天气/维基/搜索/推理等) |
| `mcpServers` | MCP 服务器配置 |
| `agents` | 多 Agent 配置 |
| `a2aServers` | A2A 服务器配置 |
| `memorySettings` | 记忆系统配置 |
| `codeSettings` | 代码解释器配置 |
| `CLISettings` | CLI 开发环境配置 |
| `visionControlSettings` | 电脑控制配置 |
| `asrSettings` | 语音识别配置 |
| `text2imgSettings` | 文生图配置 |
| `qqBotConfig` | QQ 机器人配置 |
| `behaviorSettings` | 行为引擎配置 |
| `systemSettings` | 语言/主题/网络/代理 |
| `knowledgeBases` | 知识库列表 |
| `custom_http` | 自定义 HTTP 工具 |

---

## 九、数据流图

### 聊天数据流
```
用户输入 (前端)
    │
    ▼ WebSocket/HTTP
FastAPI /v1/chat/completions
    │
    ├→ 加载 settings → 选择 active_client (快/慢脑)
    ├→ 注入 system_prompt + 工具定义 + 知识库上下文
    ├→ 记忆检索 (Mem0)
    │
    ▼ AsyncOpenAI.chat.completions.create(stream=True)
LLM 响应 (SSE 流)
    │
    ├→ 有 tool_calls?
    │   ├→ 是 → dispatch_tool() → 结果注入消息 → 再次调用 LLM (循环)
    │   └→ 否 → 输出最终回复
    │
    ▼ SSE 推送到前端
前端渲染 (Markdown-it + KaTeX + Mermaid + highlight.js)
    │
    ├→ OmniTTS → 语音合成 → VRM 口型同步
    ├→ 记忆存储 (Mem0 异步)
    └→ 好感度提取 (正则匹配)
```

---

## 十、部署方式

### 10.1 桌面端打包
```bash
npm run build:win    # Windows NSIS 安装包
npm run build:mac    # macOS DMG
npm run build:linux  # Linux AppImage + deb
```

### 10.2 Docker 部署
```bash
docker pull ailm32442/super-agent-party:latest
docker run -d -p 3456:3456 -v ./data:/app/data ailm32442/super-agent-party:latest
```

### 10.3 Docker Compose (带网关)
```bash
docker-compose up -d
# 后端 + Nginx 网关 (JWT 认证)
# 默认账号: root / pass
```

### 10.4 源码部署
```bash
git clone https://github.com/heshengtao/super-agent-party.git
cd super-agent-party
uv sync        # 安装 Python 依赖
npm install    # 安装 Node.js 依赖
npm run dev    # 启动
```

---

## 十一、项目统计数据

| 指标 | 数值 |
|------|------|
| 后端核心代码 | ~29,000 行 (server.py 10,685 + py/ 18,696) |
| 前端核心代码 | ~17,000 行 (index.html 16,625 + JS) |
| Electron 主进程 | ~2,100 行 |
| API 端点数量 | 80+ 个 |
| WebSocket 端点 | 6 个 |
| Python 后端模块 | 53 个 |
| 支持的 IM 平台 | 8 个 |
| 支持的搜索引擎 | 9 个 |
| 支持的 TTS 引擎 | 6 个 |
| 支持的文件格式 | 30+ 种 |
| Python 依赖 | 75+ 个包 |
| Node.js 依赖 | 8 个包 |
| 前端第三方库 | 15+ 个 |
