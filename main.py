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
    except Exception:
        checks["core_nexus"] = "error"

    # 会话统计
    try:
        from src.agent.session_manager import get_session_manager
        manager = get_session_manager()
        checks["active_sessions"] = len(manager.get_active_sessions())
    except Exception:
        checks["active_sessions"] = 0

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


def _build_frontend():
    """启动时自动构建前端，失败不阻塞"""
    frontend_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "synthetix-vue")
    if not os.path.isdir(frontend_dir):
        logger.warning("前端目录不存在，跳过构建")
        return

    # 检查 npm 是否可用
    npm_cmd = shutil.which("npm")
    if npm_cmd is None:
        logger.warning("npm 未安装，跳过前端构建")
        return

    try:
        logger.info("正在自动构建前端...")
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=frontend_dir,
            shell=True,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        if result.returncode == 0:
            logger.info("前端构建完成")
        else:
            logger.warning(f"前端构建失败 (exit {result.returncode}): {result.stderr[-500:] if result.stderr else ''}")
    except subprocess.TimeoutExpired:
        logger.warning("前端构建超时 (300s)，跳过")
    except Exception as e:
        logger.warning(f"前端构建异常: {e}")


def run():
    """启动 API 服务"""
    # 初始化日志配置
    log_config.log_run()

    # 自动构建前端
    _build_frontend()

    logger.info("")
    logger.info("=" * 60)
    logger.info('Synthetix API 服务启动')

    # 打印访问地址（同时使用 print 和 logger 确保显示）
    base_url = f"http://127.0.0.1:{config.api_host}"
    # 同时记录到日志
    logger.info("API 服务访问地址:")
    logger.info(f"  ├─ Web 界面:              {base_url}")
    logger.info(f"  ├─ API 文档 (Swagger UI): {base_url}/docs")
    logger.info(f"  ├─ API 文档 (ReDoc):      {base_url}/redoc")
    logger.info(f"  └─ OpenAPI Schema:        {base_url}/openapi.json")
    logger.info("=" * 60)
    logger.info("")
    # 使用 Alembic 初始化数据库
    try:
        init_database_with_alembic()
    except Exception as e:
        logging.error(f"数据库初始化失败: {str(e)}", exc_info=True)
        raise
    # 启动服务
    uvicorn.run(
        app='main:app',
        host="127.0.0.1",
        port=config.api_host,
        reload=True,
        log_config=None  # 使用自定义日志配置
    )


if __name__ == '__main__':
    run()
