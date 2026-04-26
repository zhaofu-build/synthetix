"""
运行时资源监控与自动降级

启动时检测系统资源，运行时定期检查，超过阈值自动降级。
"""
import os
import logging
import platform
from typing import Dict, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ResourceProfile:
    """系统资源配置"""
    cpu_count: int = 0
    memory_total_gb: float = 0.0
    memory_available_gb: float = 0.0
    disk_free_gb: float = 0.0
    gpu_available: bool = False
    gpu_name: str = ""
    platform: str = ""

    # Auto-degraded settings
    max_parallel_ffmpeg: int = 2
    gpu_acceleration: bool = True
    proxy_quality: float = 0.5
    crf: int = 23


def detect_system_resources() -> ResourceProfile:
    """启动时检测系统资源"""
    profile = ResourceProfile()

    # CPU
    try:
        profile.cpu_count = os.cpu_count() or 4
    except Exception:
        profile.cpu_count = 4

    # Memory
    try:
        import psutil
        mem = psutil.virtual_memory()
        profile.memory_total_gb = round(mem.total / (1024 ** 3), 1)
        profile.memory_available_gb = round(mem.available / (1024 ** 3), 1)
    except ImportError:
        profile.memory_total_gb = 8.0
        profile.memory_available_gb = 4.0

    # Disk
    try:
        import shutil
        usage = shutil.disk_usage(os.path.expanduser("~"))
        profile.disk_free_gb = round(usage.free / (1024 ** 3), 1)
    except Exception:
        profile.disk_free_gb = 50.0

    # GPU
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            profile.gpu_available = True
            profile.gpu_name = result.stdout.strip().split("\n")[0]
    except Exception:
        profile.gpu_available = False

    profile.platform = platform.system()

    # Auto-adjust based on resources
    _apply_auto_degradation(profile)

    logger.info(f"System resources: CPU={profile.cpu_count}, RAM={profile.memory_total_gb}GB, "
                f"GPU={profile.gpu_name or 'None'}, Disk={profile.disk_free_gb}GB free")
    return profile


def _apply_auto_degradation(profile: ResourceProfile):
    """根据资源自动调整参数"""
    # Low memory → reduce parallel FFmpeg, disable GPU
    if profile.memory_total_gb < 4:
        profile.max_parallel_ffmpeg = 1
        profile.gpu_acceleration = False
        profile.proxy_quality = 0.25
        profile.crf = 28
        logger.info("Low memory mode: reduced parallelism, GPU disabled")
    elif profile.memory_total_gb < 8:
        profile.max_parallel_ffmpeg = 2
        profile.proxy_quality = 0.33
        profile.crf = 26
    elif profile.memory_total_gb < 16:
        profile.max_parallel_ffmpeg = min(profile.cpu_count, 3)
    else:
        profile.max_parallel_ffmpeg = min(profile.cpu_count, 4)

    # No GPU → disable GPU acceleration
    if not profile.gpu_available:
        profile.gpu_acceleration = False

    # Low disk space → higher compression
    if profile.disk_free_gb < 5:
        profile.crf = 30
        logger.warning(f"Low disk space ({profile.disk_free_gb}GB), using high compression")


def check_runtime_resources(profile: ResourceProfile) -> Dict[str, any]:
    """运行时检查资源状态，返回警告"""
    warnings = []

    try:
        import psutil
        mem = psutil.virtual_memory()
        if mem.percent > 90:
            warnings.append(f"内存使用率 {mem.percent}%，建议关闭其他应用")
            profile.max_parallel_ffmpeg = max(1, profile.max_parallel_ffmpeg - 1)
        if mem.percent > 95:
            warnings.append("内存严重不足，已关闭 GPU 加速")
            profile.gpu_acceleration = False

        import shutil
        usage = shutil.disk_usage(os.path.expanduser("~"))
        free_gb = usage.free / (1024 ** 3)
        if free_gb < 1:
            warnings.append(f"磁盘剩余 {free_gb:.1f}GB，渲染可能失败")
    except ImportError:
        pass

    return {"warnings": warnings, "degraded": len(warnings) > 0}


# Global singleton
_profile: Optional[ResourceProfile] = None


def get_resource_profile() -> ResourceProfile:
    """获取全局资源配置（首次调用时检测）"""
    global _profile
    if _profile is None:
        _profile = detect_system_resources()
    return _profile


def refresh_resource_profile() -> ResourceProfile:
    """重新检测系统资源"""
    global _profile
    _profile = detect_system_resources()
    return _profile
