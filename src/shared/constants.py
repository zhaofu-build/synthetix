"""常量定义模块

集中管理项目中的所有常量，避免魔法数字
"""
from enum import Enum


# 文件大小常量
class FileSize:
    """文件大小限制（字节）"""
    MAX_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB
    MAX_CHUNK_SIZE = 1024 * 1024  # 1MB 分块大小
    MAX_VIDEO_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MAX_AUDIO_SIZE = 100 * 1024 * 1024  # 100MB


# 分页常量
class Pagination:
    """分页配置"""
    DEFAULT_PAGE = 1
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 1000
    MIN_PAGE_SIZE = 1


# 视频处理常量
class VideoProcessing:
    """视频处理配置"""
    DEFAULT_OUTPUT_FORMAT = "mp4"
    DEFAULT_WIDTH = 1920
    DEFAULT_HEIGHT = 1080
    DEFAULT_FPS = 30

    # 质量参数
    DEFAULT_CRF = 23
    MIN_CRF = 18
    MAX_CRF = 35

    # 比特率参数
    DEFAULT_MAX_BITRATE = "8000k"
    DEFAULT_AUDIO_BITRATE = "192k"

    # 速度/音量范围
    MIN_SPEED_FACTOR = 0.1
    MAX_SPEED_FACTOR = 10.0
    MIN_VOLUME_FACTOR = 0.0
    MAX_VOLUME_FACTOR = 5.0

    # 支持的输出格式
    SUPPORTED_FORMATS = ["mp4", "avi", "mov", "mkv", "flv", "wmv"]


# 音频处理常量
class AudioProcessing:
    """音频处理配置"""
    DEFAULT_SAMPLE_RATE = 44100
    DEFAULT_CHANNELS = 2
    DEFAULT_BITRATE = 192000

    # 支持的音频格式
    SUPPORTED_FORMATS = ["wav", "mp3", "flac", "aac", "m4a", "ogg"]


# TTS/语音合成常量
class TTSConfig:
    """语音合成配置"""
    DEFAULT_SPEED = 1.0
    MIN_SPEED = 0.1
    MAX_SPEED = 5.0

    DEFAULT_TEMPERATURE = 0.5
    MIN_TEMPERATURE = 0.0
    MAX_TEMPERATURE = 2.0

    DEFAULT_TOP_P = 0.5
    MIN_TOP_P = 0.0
    MAX_TOP_P = 1.0

    DEFAULT_REPETITION_PENALTY = 1.35
    MIN_REPETITION_PENALTY = 0.0
    MAX_REPETITION_PENALTY = 5.0

    DEFAULT_SEED = 42
    SEED_MIN = 0  # 随机种子最小值
    SEED_MAX = 100000  # 随机种子最大值


# 字幕常量
class Subtitle:
    """字幕配置"""
    SUPPORTED_FORMATS = ["srt", "ass", "vtt", "ssa"]

    # 支持的语言
    SUPPORTED_LANGUAGES = ["zh", "en", "ja", "ko", "es", "fr", "de", "ru", "ar"]

    # Whisper 模型
    WHISPER_MODELS = ["tiny", "base", "small", "medium", "large"]

    DEFAULT_MODEL = "base"
    DEFAULT_FORMAT = "srt"


# 视频类型常量
class VideoType(str, Enum):
    """视频类型枚举"""
    UNUSED = 0  # 未使用
    IN_USE = 1  # 使用中
    PEXELS = 2  # Pexels来源
    PIXABAY = 3  # Pixabay来源
    LOCAL = 4  # 本地上传
    GENERATED = 5  # AI生成


# HTTP 状态码
class HTTPStatus:
    """HTTP 状态码"""
    OK = 200
    CREATED = 201
    NO_CONTENT = 204
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


# 任务状态
class TaskStatus:
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# 时间常量
class TimeConstants:
    """时间相关常量（秒）"""
    ONE_MINUTE = 60
    ONE_HOUR = 3600
    ONE_DAY = 86400

    TASK_CLEANUP_AGE = ONE_HOUR  # 任务清理时间（1小时）
    SESSION_TIMEOUT = 24 * ONE_HOUR  # 会话超时（24小时）


# API 相关常量
class APIConfig:
    """API 配置"""
    DEFAULT_API_PORT = 9527
    DEFAULT_WEB_PORT = 9528

    # 请求超时
    DEFAULT_TIMEOUT = 30
    LONG_RUNNING_TIMEOUT = 300  # 5分钟


# 目录常量
class DirectoryConfig:
    """目录配置"""
    UPLOAD_DIR = "static/uploads/"
    SOURCE_VIDEOS_DIR = "static/source_videos/"
    SOURCE_BGM_DIR = "static/source_bgm/"
    SOURCE_AUDIOS_DIR = "static/source_timbre/"
    LOG_DIR = "static/loginfo/"

    # 模型缓存
    MODEL_CACHE_DIR = "D:/hf-model"


# 正则表达式模式
class RegexPatterns:
    """常用正则表达式"""
    EMAIL = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    URL = r'^https?://[^\s/$.?#].[^\s]*$'
    TIME_FORMAT = r'^\d{2}:\d{2}:\d{2}$'  # HH:MM:SS
    HEX_COLOR = r'^#[0-9A-Fa-f]{6}$'


# Agent 配置常量
class AgentConfig:
    """Agent 配置"""
    MAX_HISTORY_MESSAGES = 50      # 单会话最大消息条数
    HISTORY_TRUNCATE_KEEP = 10     # 截断时保留最近的消息条数
    SESSION_CLEANUP_INTERVAL = 600  # 会话清理间隔（秒），10分钟
    SESSION_DB_TTL = 86400          # DB 中会话保留时长（秒），24 小时
    MAX_ACTION_RETRIES = 2          # 工具执行最大重试次数
    MAX_LLM_PARSE_RETRIES = 1       # LLM JSON 解析最大重试次数
