import os
import subprocess
import asyncio
import shutil
import uvicorn
import logging
from contextlib import asynccontextmanager

os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"
os.environ['HF_HOME'] = 'D:/hf-model'

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from src import log_config, config
from src.infrastructure.db.alembic_manager import init_database_with_alembic
from src.interfaces.api.svc_api import router as audio_api
from src.interfaces.api.tool_api import router as tool_api
from src.interfaces.api.video_api import router as video_api
from src.interfaces.api.llm_clip_api import router as ai_api
from src.interfaces.api.core_nexus_api import router as core_nexus_api
from src.interfaces.api.agent_api import router as agent_api
from src.interfaces.api.project_api import router as project_api
from src.interfaces.api.task_api import router as task_api
from src.interfaces.api.ws_api import router as ws_api
from src.interfaces.api.mcp_api import router as mcp_api
from src.interfaces.api.extension_api import router as extension_api
from src.interfaces.api.comic_api import router as comic_api

from src.shared.utils import file_util

# 导入异常处理器
from src.shared.exceptions import register_exception_handlers


logger = logging.getLogger(__name__)


async def _session_cleanup_loop():
    """定期清理过期会话"""
    from src.shared.constants import AgentConfig
    from src.agent.session_manager import get_session_manager

    while True:
        await asyncio.sleep(AgentConfig.SESSION_CLEANUP_INTERVAL)
        try:
            manager = get_session_manager()
            cleaned = manager.cleanup_expired_sessions()
            if cleaned > 0:
                logger.info(f"清理了 {cleaned} 个过期会话")
        except Exception as e:
            logger.error(f"会话清理失败: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时执行
    # 关键：在uvicorn工作进程中重新初始化日志配置
    log_config.log_run()
    logger.info("应用启动，开始初始化...")
    try:
        # 清除upload_dir
        file_util.clean_upload_dir(config.UPLOAD_DIR)
        logger.info("临时文件目录清理完成")
    except Exception as e:
        logger.error(f"应用启动初始化失败: {str(e)}", exc_info=True)

    # 启动会话清理后台任务
    cleanup_task = asyncio.create_task(_session_cleanup_loop())

    # 加载扩展并注册工具
    try:
        from src.agent.extension_loader import load_extensions, register_extension_tools
        load_extensions()
        register_extension_tools()
    except Exception as e:
        logger.warning(f"扩展加载失败: {e}")

    # 注册全局拦截器
    try:
        from src.agent.tool_registry import registry
        from src.agent.interceptors import register_default_interceptors
        register_default_interceptors(registry)
    except Exception as e:
        logger.warning(f"拦截器注册失败: {e}")

    # 从 settings.json 同步配置到运行时
    try:
        from src.shared.utils.config_manager import get as cfg_get
        _px_key = cfg_get('pixabay_api_key', '')
        if _px_key:
            config.pixabay_api_key = _px_key
        _va_keys = cfg_get('video_api_keys', '')
        if _va_keys:
            config.video_api_keys = _va_keys
    except Exception as e:
        logger.warning(f"配置同步失败: {e}")

    yield

    # 关闭时执行
    cleanup_task.cancel()
    # 关闭 CoreNexusClient 连接
    try:
        from src.shared.utils.core_nexus_client import get_client
        get_client().close()
    except Exception:
        pass
    logger.info("应用关闭")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="Synthetix API",
    description="Synthetix AI工作流化项目 API 接口",
    version="1.0.0",
    lifespan=lifespan
)

# 注册全局异常处理器
register_exception_handlers(app)

# 注册 API 路由（RESTful 风格，带前缀）
app.include_router(audio_api, prefix="/api/audios", tags=["音频服务"])
app.include_router(tool_api, prefix="/api/tools", tags=["工具服务"])
app.include_router(video_api, prefix="/api/videos", tags=["视频服务"])
app.include_router(ai_api, prefix="/api/ai", tags=["AI服务"])
app.include_router(core_nexus_api, prefix="/api/nexus", tags=["Core-Nexus-AI"])
app.include_router(agent_api, prefix="/api/agent", tags=["对话Agent"])
app.include_router(project_api, prefix="/api/projects", tags=["视频项目"])
app.include_router(task_api, prefix="/api/tasks", tags=["任务管理"])
app.include_router(ws_api, tags=["WebSocket"])
app.include_router(mcp_api, prefix="/api/mcp", tags=["MCP工具"])
app.include_router(extension_api, prefix="/api/extensions", tags=["扩展管理"])
app.include_router(comic_api, prefix="/api/comic-projects", tags=["漫剧项目"])
# app.include_router(video_generation_api, tags=["视频生成"])

# ⚠️ 重要：CORS 中间件必须在其他中间件之前添加
# 从环境变量读取允许的来源，支持多域名（逗号分隔）
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,  # 从配置读取允许的来源
    allow_credentials=True,
    allow_methods=["*"],  # 允许所有方法
    allow_headers=["*"],  # 允许所有头部
)

# 配置静态文件目录
os.makedirs(config.UPLOAD_DIR, exist_ok=True)

# ── 前端 SPA 挂载 ──────────────────────────────────────────────
FRONTEND_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetix-vue", "dist")
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _safe_file(base: str, rel_path: str):
    """返回安全绝对路径，防止目录穿越；不在 base 内则返回 None"""
    base_resolved = Path(base).resolve()
    target = (base_resolved / rel_path).resolve()
    if str(target).startswith(str(base_resolved)):
        return str(target) if target.is_file() else None
    return None


@app.get("/")
async def serve_frontend_index():
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)
    return JSONResponse({"message": "前端未构建，请先执行: cd synthetix-vue && npm run build"}, status_code=404)


@app.get("/api/metrics/ai")
async def ai_metrics(hours: int = 24):
    """AI 调用统计"""
    from src.shared.utils.observability import get_ai_stats
    return get_ai_stats(hours)


# ── 平台适配预设 ──
PLATFORM_PRESETS = {
    "douyin": {
        "name": "抖音/TikTok", "aspect": "9:16", "width": 1080, "height": 1920,
        "max_duration": 300, "codec": "h264", "bitrate": "8M",
        "fps": 30, "tips": "竖屏优先，15-60秒最佳，添加字幕提升完播率",
    },
    "bilibili": {
        "name": "B站/Bilibili", "aspect": "16:9", "width": 1920, "height": 1080,
        "max_duration": 3600, "codec": "h264", "bitrate": "12M",
        "fps": 30, "tips": "横屏为主，支持4K，中长视频需章节标记",
    },
    "youtube": {
        "name": "YouTube", "aspect": "16:9", "width": 1920, "height": 1080,
        "max_duration": 43200, "codec": "h264", "bitrate": "15M",
        "fps": 30, "tips": "16:9 标准，4K可选，Shorts用9:16 60秒内",
    },
    "xiaohongshu": {
        "name": "小红书", "aspect": "3:4", "width": 1080, "height": 1440,
        "max_duration": 300, "codec": "h264", "bitrate": "6M",
        "fps": 30, "tips": "3:4或1:1，图文视频化效果佳，封面至关重要",
    },
    "kuaishou": {
        "name": "快手", "aspect": "9:16", "width": 1080, "height": 1920,
        "max_duration": 300, "codec": "h264", "bitrate": "8M",
        "fps": 30, "tips": "竖屏优先，前3秒抓眼球，节奏要快",
    },
    "weibo": {
        "name": "微博", "aspect": "16:9", "width": 1920, "height": 1080,
        "max_duration": 900, "codec": "h264", "bitrate": "10M",
        "fps": 30, "tips": "横屏为主，5分钟内效果好，清晰度优先",
    },
}


@app.get("/api/platform-presets")
async def get_platform_presets():
    """获取平台适配预设列表"""
    from src.shared.models.response import success_response
    return success_response(data=PLATFORM_PRESETS)


@app.get("/health")
async def health_check():
    checks = {"status": "ok", "version": "1.0.0"}

    # 数据库检查
    try:
        from src.infrastructure.db.session import get_db_context
        from sqlalchemy import text
        with get_db_context() as db:
            db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"

    # ffmpeg 检查
    checks["ffmpeg"] = "ok" if shutil.which("ffmpeg") else "unavailable"

    # Core-Nexus 检查
    try:
        from src.shared.utils.core_nexus_client import get_client
        client = get_client()
        checks["core_nexus"] = "configured" if client.base_url else "not_configured"
        key_stats = client.key_pool_stats
        if key_stats:
            checks["api_key_pool"] = key_stats
    except Exception:
        checks["core_nexus"] = "error"

    # 会话统计
    try:
        from src.agent.session_manager import get_session_manager
        manager = get_session_manager()
        checks["active_sessions"] = len(manager.get_active_sessions())
    except Exception:
        checks["active_sessions"] = 0

    # 资源状态
    try:
        from src.shared.utils.resource_monitor import get_resource_profile
        profile = get_resource_profile()
        checks["resources"] = {
            "cpu": profile.cpu_count,
            "memory_gb": profile.memory_total_gb,
            "gpu": profile.gpu_name or "none",
            "disk_free_gb": profile.disk_free_gb,
            "gpu_acceleration": profile.gpu_acceleration,
            "max_parallel": profile.max_parallel_ffmpeg,
        }
    except Exception:
        pass

    if any(v.startswith("error") if isinstance(v, str) else False for v in checks.values()):
        checks["status"] = "degraded"

    return checks


@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    # 1) 后端静态文件 (/static/...)
    if full_path.startswith("static/"):
        fpath = _safe_file(_BASE_DIR, full_path)
        if fpath:
            return FileResponse(fpath)

    # 2) 前端构建产物 (assets/..., favicon.ico 等)
    fpath = _safe_file(FRONTEND_DIST, full_path)
    if fpath:
        return FileResponse(fpath)

    # 3) SPA 回退 → index.html（客户端路由由 Vue Router 处理）
    index = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.isfile(index):
        return FileResponse(index)

    from fastapi.responses import JSONResponse
    return JSONResponse({"detail": "Not Found"}, status_code=404)


def _start_tauri():
    """启动 Tauri 桌面窗口"""
    tauri_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetix-tauri")
    if not os.path.isdir(tauri_dir):
        logger.warning("synthetix-tauri 目录不存在，跳过桌面窗口启动")
        return

    npx_cmd = shutil.which("npx") or shutil.which("npx.cmd")
    if npx_cmd is None:
        logger.warning("npx 未安装，跳过桌面窗口启动")
        return

    try:
        logger.info("正在启动 Tauri 桌面窗口...")
        subprocess.Popen(
            f'"{npx_cmd}" tauri dev',
            cwd=os.path.dirname(os.path.abspath(__file__)),
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Tauri 桌面窗口启动中...")
    except Exception as e:
        logger.warning(f"Tauri 启动异常: {e}")


def _wait_for_api(port, timeout=15):
    """等待 API 服务就绪"""
    import urllib.request
    import urllib.error
    import time
    url = f"http://127.0.0.1:{port}/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except (urllib.error.URLError, ConnectionError, OSError):
            time.sleep(0.3)
    return False


def _build_frontend():
    """构建前端 dist"""
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetix-vue")
    npm_cmd = shutil.which("npm") or shutil.which("npm.cmd")
    if not npm_cmd:
        logger.warning("npm 未找到，跳过前端构建")
        return False
    logger.info("正在构建前端...")
    result = subprocess.run(
        f'"{npm_cmd}" run build',
        cwd=frontend_dir,
        shell=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='replace',
    )
    if result.returncode != 0:
        logger.error(f"前端构建失败:\n{result.stderr}")
        return False
    logger.info("前端构建完成")
    return True


def run():
    """启动桌面应用（后端 API + Tauri 窗口）"""
    import threading

    log_config.log_run()

    logger.info("")
    logger.info("=" * 60)
    logger.info('Synthetix 桌面应用启动')

    # 初始化数据库
    try:
        init_database_with_alembic()
    except Exception as e:
        logging.error(f"数据库初始化失败: {str(e)}", exc_info=True)
        raise

    # 先构建前端（避免 Tauri beforeDevCommand 并行导致覆盖 dist）
    _build_frontend()

    # 后台线程启动 uvicorn API 服务
    def _run_api():
        uvicorn.run(
            app='main:app',
            host="127.0.0.1",
            port=config.api_host,
            log_config=None,
        )

    api_thread = threading.Thread(target=_run_api, daemon=True)
    api_thread.start()

    # 等待 API 服务就绪
    if _wait_for_api(config.api_host):
        logger.info(f"API 后端已就绪: http://127.0.0.1:{config.api_host}")
    else:
        logger.warning(f"API 后端未能在超时内就绪: http://127.0.0.1:{config.api_host}")

    # 前台运行 Tauri 桌面窗口
    npx_cmd = shutil.which("npx") or shutil.which("npx.cmd")
    if npx_cmd:
        # 确保 cargo 在 PATH 中
        cargo_dir = os.path.expanduser("~/.cargo/bin")
        if os.path.isdir(cargo_dir) and cargo_dir not in os.environ.get("PATH", ""):
            os.environ["PATH"] = cargo_dir + os.pathsep + os.environ.get("PATH", "")
        logger.info("正在启动 Tauri 桌面窗口...")
        try:
            subprocess.run(
                f'"{npx_cmd}" tauri dev',
                cwd=os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetix-tauri"),
                shell=True,
            )
        except KeyboardInterrupt:
            logger.info("用户中断，正在关闭...")
    else:
        logger.warning("npx 未安装，回退到 Web 模式")
        uvicorn.run(
            app='main:app',
            host="127.0.0.1",
            port=config.api_host,
            reload=True,
            log_config=None,
        )


if __name__ == '__main__':
    run()
