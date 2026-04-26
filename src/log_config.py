import logging
import os
from datetime import datetime


# 基础版 - 每次启动生成当天日志文件
# def setup_basic_logging():
#     # 创建日志目录
#     log_dir = "static/loginfo"
#     os.makedirs(log_dir, exist_ok=True)
#
#     # 生成带日期的文件名（格式：2024-05-15.log）
#     current_date = datetime.now().strftime("%Y-%m-%d")
#     log_filename = os.path.join(log_dir, f"{current_date}.log")
#
#     # 配置日志系统
#     logging.basicConfig(
#         level=logging.INFO,
#         format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
#         handlers=[
#             logging.FileHandler(log_filename, encoding="utf-8"),
#             logging.StreamHandler()
#         ]
#     )


# 增强版 - 支持运行时自动按天滚动（推荐）
def setup_advanced_logging():
    from logging.handlers import TimedRotatingFileHandler
    import sys

    # 创建日志目录
    log_dir = "static/loginfo"
    os.makedirs(log_dir, exist_ok=True)

    # 直接使用当天日期作为文件名
    current_date = datetime.now().strftime('%Y-%m-%d')
    log_filename = os.path.join(log_dir, f"{current_date}.log")

    # 自定义Handler，强制每次flush
    class FlushingTimedRotatingFileHandler(TimedRotatingFileHandler):
        def emit(self, record):
            super().emit(record)
            self.flush()  # 每次写入后立即刷新

    # 配置按天滚动的Handler
    file_handler = FlushingTimedRotatingFileHandler(
        filename=log_filename,  # 使用当天日期的文件名
        when='midnight',  # 每天午夜滚动
        interval=1,  # 每天间隔
        backupCount=30,  # 保留30天日志
        encoding='utf-8',
        delay=False  # 立即打开文件，不延迟
    )
    file_handler.setLevel(logging.INFO)  # 文件记录INFO及以上级别（包括INFO、WARNING、ERROR）

    # 配置控制台Handler，确保所有级别的日志都能打印
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.DEBUG)  # 控制台显示所有级别的日志

    # 统一的日志格式
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    # 配置日志系统
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # root logger设置为最低级别

    # 清除之前的handlers，避免重复
    root_logger.handlers.clear()

    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # 抑制第三方库的 DEBUG 日志
    for _name in ('httpcore', 'httpx', 'urllib3', 'asyncio', 'multipart'):
        logging.getLogger(_name).setLevel(logging.WARNING)


def log_run():
    setup_advanced_logging()  # 或 setup_basic_logging()
    logging.info("日志系统已初始化")
