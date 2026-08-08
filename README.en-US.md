

# Synthetix

Desktop AI video editing platform based on Tauri 2.0 + Vue 3 + FastAPI, streamlining the video creation process through AI capabilities.

## Features

### AI Conversational Editing
- **Conversational Editing** — Describe requirements in natural language, and the Agent automatically invokes tools to complete editing
- **SSE Streaming Response** — Step-by-step real-time display of thinking process, tool execution, and results
- **Deep Research Mode** — Multi-stage asset analysis → plan formulation → execution, handling complex editing requirements
- **93 Built-in Tools** — Video trimming, merging, subtitles, effects, audio processing, AI analysis, etc.

### Editor
- **Unified Editor** — Three-column layout: Workspace (editing plan/audio) | AI Chat | Asset Library + Preview
- **Project Management** — Create/switch/save/export projects, debounced auto-saving
- **Smart Editing Plan** — AI automatically generates editing plans based on scripts and assets, applied to the timeline
- **Video Rendering** — Local FFmpeg rendering, supports multiple outputs

### AI Capabilities (via core-nexus-ai)
- **LLM** — Conversational reasoning, intent understanding, plan planning
- **TTS** — Speech synthesis, voice cloning
- **ASR** — Speech recognition, video transcription
- **VL** — Video understanding, content analysis
- **Music Generation** — Text-to-background music generation

### Assets & Processing
- **Asset Management** — Local upload / online search (Pexels, Pixabay), tag filtering, AI auto-analysis of descriptions
- **Audio/Video Processing** — Format conversion, subtitle extraction & translation, vocal track separation, batch compression
- **BGM Management** — Music library management, AI song selection, AI music generation
- **Video Download** — One-click download videos from thousands of platforms (yt-dlp)
- **Comic Project Production** — Image-to-video conversion, AI-assisted comic project creation

### Extensibility
- **Extensions/Plugins** — Custom extensions inject tools and system prompts
- **MCP Protocol** — Dynamically connect to external tool servers
- **Skill System** — Markdown-defined reusable skills
- **Knowledge Base** — Project-level BM25 search, recording analysis results and notes
- **Browser Automation** — CDP protocol controls browser for asset searching

## Tech Stack

| Layer | Technology |
|-------|------------|
| Desktop Shell | Tauri 2.0 (Rust) |
| Backend | Python 3.11, FastAPI, SQLAlchemy, Alembic, FFmpeg |
| Frontend | Vue 3, Vite, Pinia, Element Plus, Vue Router, vue-i18n |
| AI Service | core-nexus-ai (LLM, TTS, ASR, VL, Music Generation) |
| Database | SQLite |
| Deployment | Docker, docker-compose |

## Quick Start

### 1. Install Dependencies

```bash
# Python dependencies
pip install -r requirements.txt

# Frontend dependencies
cd synthetix-vue && npm install

# Tauri CLI (desktop app build)
cd synthetix-tauri && npm install

# Rust (required for Tauri)
winget install Rustlang.Rustup
```

### 2. Install FFmpeg

Download from [FFmpeg Builds](https://github.com/BtbN/FFmpeg-Builds/releases), and place `ffmpeg.exe` and `ffprobe.exe` into the `ffmpeg/` folder at the project root.

### 3. Configuration

Copy `.env.example` to `.env` and fill in the configuration:

```env
CORE_NEXUS_BASE_URL=http://your-core-nexus-server:port
LLM_KEY=your_api_key
CORS_ORIGINS=*
```

Optional configuration:

```env
API_PORT=9527                  # API port
FAST_MODEL=                    # Fast model (short text/simple queries)
SLOW_MODEL=                    # Main model (complex tasks, default)
FAST_MODEL_THRESHOLD=100       # Fast model message length threshold
CHROME_CDP_URL=                # CDP browser address (browser automation)
```

### 4. Initialize Database

```bash
alembic upgrade head
```

### 5. Start

```bash
# Desktop mode (one-click start backend API + Tauri window)
python main.py

# Or frontend dev mode (hot reload, port 9528, requires running backend simultaneously)
cd synthetix-vue && npm run dev
```

- Swagger UI: http://127.0.0.1:9527/docs
- Health Check: http://127.0.0.1:9527/health
- Frontend Dev Mode: http://127.0.0.1:9528

### Desktop App Packaging

```bash
python build_backend.py    # PyInstaller package Python backend into exe
cd synthetix-tauri         # Generate .msi and .exe installers
npx tauri build
```

## Docker Deployment

```bash
docker-compose up --build
```

Port `9527`, mounts `./src/db` (database) and `./static` (asset files).

## Project Structure

```
src/
├── agent/                        # Agent System
│   ├── react_agent.py            #   ReAct Agent (TAOR loop + SSE streaming)
│   ├── tool_registry.py          #   93 Tool Registrations (Pydantic validation + Hooks + Permissions)
│   ├── session_manager.py        #   Session Management (Memory + DB dual-write)
│   ├── mcp_client.py             #   MCP Protocol Client
│   ├── extension_loader.py       #   Extension/Plugin Loading (Scans src/extensions/)
│   ├── skill_loader.py           #   Markdown Skill Loading (Scans src/skills/)
│   ├── project_memory.py         #   Project-Level Preference Memory
│   ├── knowledge_base.py         #   BM25 Knowledge Base
│   └── multi_agent.py            #   Multi-Agent Collaboration (Plan→Execute→Review)
├── extensions/                   # Extensions/Plugins (e.g., subtitle style presets)
├── skills/                       # Markdown skill definitions
├── scripts/                      # Utility scripts
├── domain/entities/              # SQLAlchemy data models
├── application/services/         # Business logic (video/audio processing, LLM, FFmpeg, rendering)
├── interfaces/api/               # FastAPI routes (12 modules)
├── shared/                       # Shared models, utilities, core-nexus client, CDP browser
└── infrastructure/               # Database sessions, Repository layer

synthetix-vue/src/                # Frontend Vue 3 + Vite + Pinia + Element Plus
├── api/modules/                  # Backend API call modules
├── store/modules/                # Pinia state management
├── components/editor/            # Unified editor components
├── locales/                      # Internationalization (zh-CN, en-US)
└── utils/                        # Markdown rendering, API wrappers

synthetix-tauri/                  # Tauri 2.0 Desktop App (Rust)
├── src/main.rs, lib.rs           # Rust entrypoints (sidecar startup)
├── tauri.conf.json               # Tauri configuration
├── capabilities/                 # Permission declarations
├── binaries/                     # Sidecar placement directory
└── icons/                        # App icons

config/                           # Layered configuration (default.json + settings.json)
```

## Development Commands

```bash
# Database migrations
alembic revision --autogenerate -m "description"
alembic upgrade head

# Frontend
cd synthetix-vue
npm run dev          # Dev server (port 9528)
npm run build        # Production build
npm run lint         # Lint code
npm run format       # Format code

# Tests
pytest tests/unit/ -v
```

## API Overview

| Path Prefix | Module | Description |
|-------------|---------|-------------|
| `/api/agent` | agent_api | AI chat, streaming responses, tool execution |
| `/api/projects` | project_api | Project CRUD, timeline, plans, rendering |
| `/api/videos` | video_api | Video management, processing, transcription |
| `/api/audios` | svc_api | Voice, TTS, audio separation/merging |
| `/api/nexus` | core_nexus_api | AI service proxy (LLM/TTS/ASR/VL/Music) |
| `/api/tools` | tool_api | Upload, configuration management, logs |
| `/api/tasks` | task_api | Task center |
| `/api/mcp` | mcp_api | MCP Server management |
| `/api/extensions` | extension_api | Extension management |
| `/api/ai` | llm_clip_api | Keyword assets, transitions |
| `/api/comic-projects` | comic_api | Comic project management |
| `/ws` | ws_api | WebSocket (chat/rendering/notifications) |

## License

Apache License 2.0
