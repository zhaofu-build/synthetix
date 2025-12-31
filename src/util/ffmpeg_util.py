import subprocess
import platform
import shutil
from pathlib import Path
import logging as logger


def check_cuda_support():
    # 检查ffmpeg是否支持CUDA
    cmd = ['ffmpeg', '-hwaccels']
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if result and 'cuda' in result.stdout.lower():
        return True
    return False


def check_nvidia():
    """检测NVIDIA显卡支持"""
    try:
        subprocess.run(['nvidia-smi'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except FileNotFoundError:
        return False


def should_compress(video_info):
    """判断视频是否需要压缩"""
    if not video_info:
        return True

    # 已经是H.265编码的视频不需要压缩
    if video_info['codec'].lower() in ['hevc', 'h265', 'x265']:
        logger.info("视频已经是H.265编码，跳过压缩")
        return False

    # 低码率视频不需要压缩
    mb_per_minute = video_info['file_size'] / (1024 * 1024) / (video_info['duration'] / 60)
    if mb_per_minute < 10:  # 每分钟小于10MB
        logger.info(f"视频码率已很低({mb_per_minute:.1f}MB/min)，跳过压缩")
        return False

    return True


def detect_gpu_accelerator():
    """自动检测系统支持的GPU加速类型"""
    try:
        # 检测NVIDIA GPU
        result = subprocess.run(['nvidia-smi'], capture_output=True, text=True)
        if result.returncode == 0 and 'NVIDIA-SMI' in result.stdout:
            logger.info("检测到NVIDIA GPU加速")
            return 'nvidia'

        # 检测macOS的VideoToolbox
        if platform.system() == 'Darwin':
            logger.info("检测到macOS VideoToolbox加速")
            return 'videotoolbox'

        # 检测VAAPI (Linux Intel/AMD)
        if shutil.which('vainfo'):
            result = subprocess.run(['vainfo'], capture_output=True, text=True)
            if result.returncode == 0 and 'vainfo' in result.stdout:
                logger.info("检测到VAAPI加速")
                return 'vaapi'

        # 检测Intel Quick Sync
        if Path('/dev/dri').exists():
            logger.info("检测到Intel Quick Sync加速")
            return 'qsv'

    except Exception as e:
        logger.error(f"GPU检测失败: {e}")

    logger.info("未检测到GPU加速，将使用CPU编码")
    return 'cpu'


def extend_accelerator(command, accelerator, preset, crf, audio_bitrate):
    logger.info(f"使用加速器: {accelerator.upper()}")
    # GPU加速配置
    gpu_params = []
    if accelerator == 'nvidia':
        gpu_params = [
            '-c:v', 'hevc_nvenc',
            '-preset', 'p7' if preset is None else preset,  # 使用高质量预设
            '-rc:v', 'vbr_hq',
            '-b_ref_mode', 'middle',
            '-spatial_aq', '1',
            '-temporal_aq', '1',
            '-qp', str(crf)  # 设置质量参数
        ]
        # 禁用CRF参数
        crf = None
    elif accelerator == 'amd':
        gpu_params = [
            '-c:v', 'hevc_amf',
            '-usage', 'transcoding',
            '-quality', 'quality' if preset is None else preset,  # 最高质量
            '-rc:v', 'vbr_peak',
            '-qp_i', str(crf),
            '-qp_p', str(crf),
            '-qp_b', str(crf),
            '-header_insertion_mode', 'idr'
        ]
        crf = None
    elif accelerator == 'qsv':
        gpu_params = [
            '-c:v', 'hevc_qsv',
            '-preset', 'best' if preset is None else preset,  # 最高质量
            '-load_plugin', 'hevc_hw',
            '-look_ahead', '1',
            '-global_quality', str(crf)
        ]
        crf = None
    elif accelerator == 'videotoolbox':  # macOS
        gpu_params = [
            '-c:v', 'hevc_videotoolbox',
            '-q:v', str(crf),  # 注意: VideoToolbox使用固定质量值
            '-allow_sw', '0'
        ]
        crf = None

    # 添加GPU参数或CPU回退
    if gpu_params:
        command.extend(gpu_params)

        # macOS特殊处理
        if accelerator == 'videotoolbox':
            command.extend(['-an'])  # 禁用音频编码加速
        else:
            command.extend(['-c:a', 'aac', '-b:a', audio_bitrate])
    else:
        # CPU模式
        command.extend([
            '-c:v', 'libx265',
            '-preset', 'slow' if preset is None else preset,
            '-c:a', 'aac',
            '-b:a', audio_bitrate
        ])
    return command


def smart_max_bitrate(video_info, default_bitrate='8000k'):
    """根据原始视频质量智能设置最大比特率"""
    if not video_info or video_info['effective_bitrate'] <= 0:
        logger.info(f"使用默认最大比特率: {default_bitrate}")
        return default_bitrate

    try:
        default_value = int(default_bitrate.replace('k', ''))
    except:
        default_value = 8000

    # 计算原始视频比特率（单位kbps）
    original_bitrate_kbps = video_info['effective_bitrate'] / 1000

    # 计算基础比特率 - 取原始比特率的70%
    max_bitrate = original_bitrate_kbps * 0.7

    # 分辨率保障下限
    if video_info['width'] >= 3840 or video_info['height'] >= 2160:  # 4K
        min_bitrate = 15000
    elif video_info['width'] >= 1920 and video_info['height'] >= 1080:  # 1080p
        min_bitrate = 5000
    elif video_info['width'] >= 1280 and video_info['height'] >= 720:  # 720p
        min_bitrate = 2000
    else:  # 更低分辨率
        min_bitrate = 1000

    # 最终比特率 - 在计算的比特率和下限之间取最大值，不超过默认值
    smart_bitrate = max(min_bitrate, min(max_bitrate, default_value))

    logger.info(f"智能比特率计算: 原始={original_bitrate_kbps:.0f}kbps, 最大={smart_bitrate:.0f}kbps")
    return f"{int(smart_bitrate)}k"


def smart_crf_selection(video_info, default_crf=20):
    """根据原始视频质量智能选择CRF值"""
    if not video_info or video_info['effective_bitrate'] <= 0:
        logger.info(f"使用默认CRF值: {default_crf}")
        return default_crf

    # 基础CRF值
    crf = default_crf

    # 分辨率调整系数 (分辨率越高，使用较低的CRF)
    resolution = video_info['width'] * video_info['height']
    if resolution >= 3840 * 2160:  # 4K
        crf -= 3
    elif resolution >= 1920 * 1080:  # 1080p
        crf -= 2
    elif resolution >= 1280 * 720:  # 720p
        crf -= 1
    else:  # 低于720p
        crf += 1

    # 帧率调整系数 (帧率越高，使用较低的CRF)
    if video_info['fps'] > 40:
        crf -= 1
    elif video_info['fps'] > 30:
        crf -= 0.5

    # 比特率调整系数 (原始比特率越高，允许使用较高的CRF)
    # 计算原始视频每分钟MB (质量指标)
    mb_per_minute = video_info['bitrate_per_minute'] / (8 * 1024)  # 比特率(kbps) -> MB/min

    if mb_per_minute < 20:  # 低质量视频
        crf += 3
    elif mb_per_minute < 50:  # 中等质量
        crf += 1
    elif mb_per_minute > 150:  # 高质量
        crf -= 2
    elif mb_per_minute > 80:  # 较高质量
        crf -= 1

    # 限制在18-28范围内
    crf = max(18, min(28, crf))

    logger.info(
        f"智能CRF计算: 原始比特率={video_info['effective_bitrate'] / 1000:.0f}kbps, 每分钟{mb_per_minute:.1f}MB, 最终CRF={crf:.1f}")
    return crf
