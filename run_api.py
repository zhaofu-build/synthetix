import os
import uvicorn
import logging
from contextlib import asynccontextmanager

os.environ['HF_ENDPOINT'] = "https://hf-mirror.com"
os.environ['HF_HOME'] = 'D:/hf-model'

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from src import log_config, config
from src.infrastructure.db.alembic_manager import init_database_with_alembic
from src.interfaces.api.svc_api import router as audio_api
from src.interfaces.api.tool_api import router as tool_api
from src.interfaces.api.video_api import router as video_api
from src.interfaces.api.llm_clip_api import router as ai_api
from src.interfaces.api.core_nexus_api import router as core_nexus_api
from src.interfaces.api.agent_api import router as agent_api
from src.interfaces.api.project_api import router as project_api

from src.shared.utils import file_util

# 导入异常处理器
from src.shared.exceptions import register_exception_handlers


logger = logging.getLogger(__name__)


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
    
    yield
    
    # 关闭时执行
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

# 配置静态文件服务
os.makedirs(config.UPLOAD_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")


def run():
    """启动 API 服务"""
    # 初始化日志配置
    log_config.log_run()
    logger.info("")
    logger.info("=" * 60)
    logger.info('Synthetix API 服务启动')
    
    # 打印访问地址（同时使用 print 和 logger 确保显示）
    base_url = f"http://127.0.0.1:{config.api_host}"
    # 同时记录到日志
    logger.info("API 服务访问地址:")
    logger.info(f"  ├─ API 文档 (Swagger UI): {base_url}/docs")
    logger.info(f"  ├─ API 文档 (ReDoc):      {base_url}/redoc")
    logger.info(f"  ├─ OpenAPI Schema:        {base_url}/openapi.json")
    logger.info(f"  └─ API 根地址:            {base_url}")
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
        app='run_api:app',
        host="127.0.0.1",
        port=config.api_host,
        reload=True,
        log_config=None  # 使用自定义日志配置
    )


if __name__ == '__main__':
    run()
