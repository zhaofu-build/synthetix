import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pathlib import Path
import multiprocessing
from multiprocessing import freeze_support
import run_api
import webbrowser
import socket
import time
import logging
import signal
import sys
import os
from src import config, log_config

# 获取日志记录器
logger = logging.getLogger(__name__)

# 创建 FastAPI 应用实例
app = FastAPI(
    title="synthetix Web",
    description="synthetix前端服务",
    version="1.0.0"
)

# 检查并挂载静态文件
dist_path = Path("dist")
if not dist_path.exists():
    logger.warning("dist 目录不存在，前端静态文件可能未构建")
else:
    app.mount("/", StaticFiles(directory="dist", html=True), name="static")


# 兜底路由处理前端 history 模式
@app.exception_handler(404)
async def custom_404_handler(request, exc: HTTPException):
    index_path = Path("dist") / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404)
    return FileResponse(index_path)


def run():
    uvicorn.run(
        "run_web:app",  # 使用字符串形式
        host="127.0.0.1",
        port=config.web_host,
        access_log=False
    )


def is_port_ready(port: int, timeout: int = 30) -> bool:
    """检测端口是否就绪

    Args:
        port: 端口号
        timeout: 超时时间（秒）

    Returns:
        bool: 端口就绪返回 True，否则返回 False
    """
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                if s.connect_ex(("127.0.0.1", port)) == 0:
                    return True
        except Exception as e:
            logger.debug(f"端口 {port} 检测异常: {e}")
        time.sleep(0.2)
    return False


def shutdown_handler(signum, frame):
    """处理关闭信号"""
    logger.info("收到关闭信号，正在优雅关闭服务...")
    sys.exit(0)


def main():
    """主函数：启动 API 和 Web 服务"""
    freeze_support()

    # 初始化日志配置
    log_config.log_run()

    # 注册信号处理器
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("=" * 60)
    logger.info("pixGallery 启动中...")
    logger.info("=" * 60)

    # 创建两个进程并设置名称
    api_process = multiprocessing.Process(
        target=run_api.run,
        name="pixGallery-API"
    )
    web_process = multiprocessing.Process(
        target=run,
        name="pixGallery-Web"
    )

    # 注意：不能设置为守护进程，因为 uvicorn reload 模式会创建子进程

    try:
        # 启动进程
        logger.info(f"启动 API 服务 (端口: {config.api_host})...")
        api_process.start()

        logger.info(f"启动 Web 服务 (端口: {config.web_host})...")
        web_process.start()

        # 检查 API 服务是否就绪
        if not is_port_ready(config.api_host, timeout=30):
            logger.error(f"API 服务启动失败或超时，请检查端口 {config.api_host} 是否被占用")
            raise RuntimeError("API 服务启动失败")
        logger.info("✓ API 服务已就绪")

        # 检查 Web 服务是否就绪
        if not is_port_ready(config.web_host, timeout=30):
            logger.error(f"Web 服务启动失败或超时，请检查端口 {config.web_host} 是否被占用")
            raise RuntimeError("Web 服务启动失败")
        logger.info("✓ Web 服务已就绪")

        # 打印所有访问地址
        web_url = f"http://localhost:{config.web_host}"

        # 打开浏览器
        logger.info(f"正在打开浏览器: {web_url}")
        webbrowser.open(web_url)

        # 保持主进程运行
        api_process.join()
        web_process.join()

    except KeyboardInterrupt:
        logger.info("\n收到中断信号，正在关闭服务...")
    except Exception as e:
        logger.error(f"服务启动失败: {str(e)}", exc_info=True)
    finally:
        # 优雅关闭进程
        for process, name in [(api_process, "API"), (web_process, "Web")]:
            if process.is_alive():
                logger.info(f"正在关闭 {name} 服务...")
                process.terminate()
                process.join(timeout=5)
                if process.is_alive():
                    logger.warning(f"{name} 服务未响应，强制终止")
                    process.kill()

        logger.info("所有服务已关闭")


if __name__ == "__main__":
    main()
