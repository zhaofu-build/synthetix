import json
import logging
import os
import threading
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Trace‑id 上下文（线程局部，可选使用）
# ---------------------------------------------------------------------------
_trace_local = threading.local()


def set_trace_id(trace_id: str):
    """为当前线程设置 trace_id，之后 JSON 日志会自动包含此字段。"""
    _trace_local.trace_id = trace_id


def clear_trace_id():
    """清除当前线程的 trace_id。"""
    _trace_local.trace_id = None


def get_trace_id() -> str:
    return getattr(_trace_local, "trace_id", "") or ""


# ---------------------------------------------------------------------------
# JSON 结构化 Formatter
# ---------------------------------------------------------------------------
class JsonFormatter(logging.Formatter):
    """当 LOG_FORMAT=json 时使用的结构化 JSON 格式化器。

    输出字段：timestamp, level, logger, message, trace_id（如果存在）。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # 仅在 trace_id 非空时包含
        trace_id = get_trace_id()
        if trace_id:
            log_entry["trace_id"] = trace_id

        # 附加异常信息（如果有）
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, ensure_ascii=False)


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

    # 是否启用 JSON 结构化日志
    use_json = os.environ.get("LOG_FORMAT", "").strip().lower() == "json"

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

    # 配置控制台Handler，输出到 stdout（确保与 print 一致，Tauri 进程能捕获）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)  # 控制台显示所有级别的日志

    # 根据 LOG_FORMAT 环境变量选择格式
    if use_json:
        formatter = JsonFormatter()
    else:
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
