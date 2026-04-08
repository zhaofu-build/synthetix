# Synthetix

AI 视频剪辑平台，通过 AI 能力简化视频创作流程。

## 功能特性

- **对话式 AI 剪辑** - 自然语言对话完成视频剪辑，支持意图识别和工具自动执行
- **工作流剪辑** - 分步流程精确控制：素材准备 → 方案配置 → BGM/渲染 → 导出
- **AI 素材获取** - 根据关键词自动搜索下载视频素材
- **视频分析与描述** - AI 自动分析视频内容生成描述
- **智能剪辑方案** - AI 根据文案和素材自动生成剪辑方案
- **语音合成（TTS）** - 支持音色克隆、自定义音色管理
- **BGM 管理** - BGM 曲库、AI 选曲、AI 生成音乐
- **AI 生成** - 文生图、图生视频、歌声转换
- **视频下载** - 支持上千个平台的视频一键下载
- **音视频处理** - 格式转换、字幕提取翻译、伴奏分离、素材压缩

## 技术栈

| 层 | 技术 |
|----|------|
| 后端 | Python, FastAPI, SQLAlchemy, Alembic, FFmpeg |
| 前端 | Vue 3, Vite, Pinia, Element Plus, Vue Router |
| AI 服务 | core-nexus-ai（LLM, TTS, ASR, VL, 音乐生成） |
| 数据库 | SQLite |

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
cd synthetix-vue && npm install
```

### 2. 安装 FFmpeg

从 [FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases) 下载 Windows 版本，将 `ffmpeg.exe` 和 `ffprobe.exe` 放入项目根目录的 `ffmpeg/` 文件夹。

### 3. 配置

复制 `.env.example` 为 `.env`，填入配置：

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=http://localhost:9528
```

### 4. 初始化数据库

```bash
alembic upgrade head
```

### 5. 启动

```bash
# 后端 API（端口 9527）
python main.py

# 前端（端口 9528）
cd synthetix-vue && npm run dev
```

- API 文档：http://127.0.0.1:9527/docs
- Web 界面：http://127.0.0.1:9528

## 项目结构

```
src/
├── agent/                    # 对话式剪辑 Agent（意图识别、槽位填充、工具执行）
├── domain/entities/          # SQLAlchemy 数据模型
├── application/services/     # 业务逻辑（视频处理、音频处理、剪辑规划、渲染）
├── interfaces/api/           # FastAPI 路由层
├── shared/                   # 公共模型、工具类、core-nexus 客户端
└── infrastructure/           # 数据库会话、Repository 层

synthetix-vue/src/
├── api/modules/              # 后端 API 调用模块
├── store/modules/            # Pinia 状态管理
├── components/               # 页面组件
├── layouts/                  # 布局
└── router/                   # 路由配置
```

## 开发命令

```bash
# 数据库迁移
alembic revision --autogenerate -m "描述"
alembic upgrade head

# 前端
cd synthetix-vue
npm run dev          # 开发服务器
npm run build        # 生产构建
npm run lint         # 代码检查
npm run format       # 代码格式化
```
