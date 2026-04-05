import os
import sys
import json
import subprocess
import shutil
import shlex
from pathlib import Path
from src.shared.utils.file_util import get_download_folder, get_file_name, get_file_suffix, get_file_name_no_suffix, del_file
from src.shared.utils import time_util, string_util, ffmpeg_util, file_util
import logging
from src import config
import time
from src.infrastructure.db.session import get_db_context
from src.domain.entities.video_source import VideoSource

logger = logging.getLogger(__name__)


def safe_path(path: str) -> str:
    """
    安全处理 FFmpeg 命令中的路径参数

    Args:
        path: 原始路径

    Returns:
        处理后的安全路径
    """
    # 统一使用正斜杠（FFmpeg 在 Windows 上也支持）
    return str(path).replace('\\', '/')


def validate_path(path: str, must_exist: bool = True) -> str:
    """
    验证并返回安全路径

    Args:
        path: 原始路径
        must_exist: 是否必须存在

    Returns:
        验证后的安全路径

    Raises:
        ValueError: 路径无效或不存在
    """
    if not path:
        raise ValueError("路径不能为空")

    # 防止路径遍历攻击
    normalized = os.path.normpath(path)
    if '..' in normalized.split(os.sep):
        raise ValueError("路径不能包含 '..'")

    if must_exist and not os.path.exists(normalized):
        raise ValueError(f"路径不存在: {normalized}")

    return safe_path(normalized)


def _video_source_to_dict(video_obj: VideoSource) -> dict:
    """将 VideoSource 对象转换为字典"""
    return {
        "id": video_obj.id,
        "video_name": video_obj.video_name,
        "web_path": video_obj.web_path,
        "local_path": video_obj.local_path,
        "duration": video_obj.duration,
        "duration_hms": video_obj.duration_hms,
        "description": video_obj.description,
        "video_type": video_obj.video_type,
        "create_time": video_obj.create_time,
        "del_flag": video_obj.del_flag,
    }


def get_video_info(input_path):
    """获取视频详细信息（编码、比特率、时长等）"""
    try:
        cmd = [
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=codec_name,bit_rate,width,height,nb_frames',
            '-show_entries', 'format=duration,size,bit_rate',
            '-of', 'json',
            str(input_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        info = json.loads(result.stdout)
        # 提取视频信息
        stream_info = info['streams'][0] if 'streams' in info and len(info['streams']) > 0 else {}
        format_info = info['format'] if 'format' in info else {}
        duration = float(format_info.get('duration', 0))
        duration_hms = time_util.seconds_to_hms(duration)
        video_info = {
            'file_name': get_file_name(input_path),
            'codec': stream_info.get('codec_name', 'unknown'),
            'width': int(stream_info.get('width', 0)),
            'height': int(stream_info.get('height', 0)),
            'duration': duration,
            'duration_hms': duration_hms,
            'file_size': int(format_info.get('size', 0)),  # 文件大小（字节）
            'video_bitrate': int(stream_info.get('bit_rate', 0)) if 'bit_rate' in stream_info else 0,
            'total_bitrate': int(format_info.get('bit_rate', 0)) if 'bit_rate' in format_info else 0,
            'frame_count': int(stream_info.get('nb_frames', 0))
        }
        # 计算实际比特率 (优先使用视频流比特率)
        if video_info['video_bitrate'] > 0:
            video_info['effective_bitrate'] = video_info['video_bitrate']
        else:
            video_info['effective_bitrate'] = video_info['total_bitrate']
        # 计算帧率
        if video_info['frame_count'] > 0 and video_info['duration'] > 0:
            video_info['fps'] = round(video_info['frame_count'] / video_info['duration'], 2)
        else:
            video_info['fps'] = 0
        # 计算每GB大小的比特率 (用于质量评估)
        if video_info['duration'] > 0:
            minutes = video_info['duration'] / 60
            video_info['bitrate_per_minute'] = (video_info['file_size'] * 8) / (1024 * minutes)  # kbps per minute
        else:
            video_info['bitrate_per_minute'] = 0
        return video_info
    except Exception as e:
        logger.error(f"获取视频信息失败 {input_path}: {e}")
        return None


def process_video(input_path, output_path=None,
                  start_time=None, end_time=None, duration=None,
                  speed_factor=None, volume_factor=None,
                  width=None, height=None,
                  cover_image=None,
                  output_format='mp4'):
    logger.debug(f"速度因子: {speed_factor}")
    logger.debug(f"音量因子: {volume_factor}")
    if speed_factor is None:
        speed_factor = 1.0
    if volume_factor is None:
        volume_factor = 1.0
    """
    综合视频处理方法（剪切/调速/分辨率/音量/封面/格式转换）
    参数说明：
    - input_path: 输入文件路径
    - output_path: 输出路径（默认自动生成）
    - start_time/end_time/duration: 时间剪切参数（格式：HH:MM:SS）
    - speed_factor: 播放速度（默认1.0不变，0.5=减速一半，2.0=加速2倍）
    - volume_factor: 音量倍数（默认1.0不变）
    - width/height: 目标分辨率（默认保持原分辨率）
    - cover_image: 封面图片路径（默认不加封面）
    - output_format: 输出格式（默认mp4）
    """
    # 基础命令
    cmd = [
        'ffmpeg',
        '-hide_banner',
        '-y'  # 覆盖输出文件
    ]
    # 添加时间剪切参数
    if start_time:
        cmd.extend(['-ss', start_time])
    # 输入文件
    cmd.extend(['-i', input_path])
    # 构建滤镜链
    video_filters = []
    audio_filters = []
    # 速度调整
    if speed_factor != 1.0:
        video_filters.append(f"setpts={1 / speed_factor}*PTS")
        audio_filters.append(f"atempo={speed_factor}")
    # 分辨率调整
    if width and height:
        video_filters.append(f"scale={width}:{height}")
    # 音量调整
    if volume_factor != 1.0:
        audio_filters.append(f"volume={volume_factor}")
    # 构建滤镜链
    filter_complex = []
    need_filter = False  # 新增判断标志
    # 视频处理分支
    video_stream = '0:v'
    if speed_factor != 1.0 or (width and height):
        video_filters = []
        if speed_factor != 1.0:
            video_filters.append(f"setpts={1 / speed_factor}*PTS")
        if width and height:
            video_filters.append(f"scale={width}:{height}")
        filter_complex.append(f"[0:v]{','.join(video_filters)}[vout]")
        video_stream = "[vout]"
        need_filter = True
    # 音频处理分支
    audio_stream = '0:a'
    if speed_factor != 1.0 or volume_factor != 1.0:
        audio_filters = []
        if speed_factor != 1.0:
            audio_filters.append(f"atempo={speed_factor}")
        if volume_factor != 1.0:
            audio_filters.append(f"volume={volume_factor}")
        filter_complex.append(f"[0:a]{','.join(audio_filters)}[aout]")
        audio_stream = "[aout]"
        need_filter = True
    # 条件添加滤镜链
    if need_filter:
        cmd.extend(['-filter_complex', ';'.join(filter_complex)])
    # 输出映射（动态调整）
    cmd += ['-map', video_stream, '-map', audio_stream]
    # 编码参数
    codec_config = {
        'mp4': {'vcodec': 'libx264', 'acodec': 'aac'},
        'webm': {'vcodec': 'libvpx-vp9', 'acodec': 'libopus'},
        'mkv': {'vcodec': 'copy', 'acodec': 'copy'},
        'avi': {'vcodec': 'libxvid', 'acodec': 'mp3'}
    }
    config = codec_config.get(output_format, codec_config['mp4'])
    cmd.extend([
        '-c:v', config['vcodec'],
        '-c:a', config['acodec'],
        '-movflags', '+faststart',
        '-crf', '23',
        '-preset', 'fast'
    ])
    # 时间参数（结束时间或持续时间）
    if duration:
        cmd.extend(['-t', duration])
    elif end_time:
        cmd.extend(['-to', end_time])
    # 输出文件
    cmd.append(output_path)
    try:
        subprocess.run(cmd, check=True)
        return output_path
    except subprocess.CalledProcessError as e:
        return f"处理失败：{e.stderr}"


# 设置封面
def set_video_cover(input_video, cover_image):
    output_path = get_download_folder() + get_file_name_no_suffix(input_video) + "(封面)" + get_file_suffix(input_video)
    command = [
        '-i', input_video,  # 输入视频文件
        '-i', cover_image,  # 封面图片文件
        '-map', '0',  # 映射第一个输入的所有流（视频和音频）
        '-map', '1',  # 映射第二个输入（封面图片）
        '-c', 'copy',  # 复制所有流，不重新编码
        '-disposition:v:0', 'default',  # 设置第一个视频流为默认显示
        '-disposition:v:1', 'attached_pic',  # 设置封面图片为附加图片
        output_path  # 输出文件
    ]
    run_ffmpeg_cmd(command)
    return "封面设置成功，文件地址为：" + output_path


# 获取指定秒的第一帧
def extract_frame(input_video, time_ss, output_image_path):
    command = [
        '-y',  # 覆盖输出文件而不询问
        '-i', input_video,  # 输入视频文件
        '-ss', time_ss,  # 指定开始时间（HH:MM:SS格式）
        '-vframes', '1',  # 只提取一帧
        '-q:v', '2',  # 控制输出质量(2-31，越低越好)
        output_image_path  # 输出图像文件
    ]
    run_ffmpeg_cmd(command)


# 获取指定时间段内每秒的第一帧
def extract_frames(input_video_path, output_dir, start_time, end_time):
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # 计算总帧数
    total_seconds = int(end_time.split(':')[-1]) - int(start_time.split(':')[-1])
    # 构建ffmpeg命令
    for i in range(total_seconds + 1):
        current_time = f"{int(start_time.split(':')[0]):02d}:{int(start_time.split(':')[1]):02d}:{int(start_time.split(':')[2]) + i:02d}"
        output_image_path = os.path.join(output_dir, f"frame_{i + 1:04d}.jpg")

        command = [
            '-i', input_video_path,  # 输入视频文件
            '-ss', current_time,  # 指定开始时间（HH:MM:SS格式）
            '-vframes', '1',  # 只提取一帧
            output_image_path  # 输出图像文件
        ]
        run_ffmpeg_cmd(command)


# 生成gif文件
def video_to_gif(input_video, start_time=None, duration=None, fps=10, scale='320:-1'):
    # 可选参数
    # input_video_path = 'path/to/your/input_video.mp4'
    # start_time = '00:00:05'  # 开始时间（HH:MM:SS格式），例如从第5秒开始
    # duration = '00:00:10'  # 持续时间（HH:MM:SS格式），例如10秒
    # fps = 10  # 帧率，每秒10帧
    # scale = '320:-1'  # 缩放比例，宽度320像素，高度按比例缩放
    output_gif_path = get_download_folder() + get_file_name_no_suffix(input_video) + ".gif"
    command = [
        '-i', input_video,  # 输入视频文件
    ]
    if start_time:
        command.extend(['-ss', start_time])  # 指定开始时间（可选）

    if duration:
        command.extend(['-t', duration])  # 指定持续时间（可选）
    if scale:
        command.extend(['-vf', f'scale={scale}'])  # 指定缩放比例（可选）
    else:
        command.extend(['-vf', 'fps=' + str(fps)])  # 设置帧率
    command.extend([
        '-pix_fmt', 'rgb24',  # 设置像素格式
        output_gif_path  # 输出GIF文件
    ])
    run_ffmpeg_cmd(command)


# 按时间间隔分割成多个视频
def extract_video_clips(input_video_path, output_dir, interval=5):
    # # 示例调用
    # input_video_path：视频url
    # output_directory：输出片段目录
    # interval： 时间间隔（秒）
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    # # 获取视频的总时长
    # duration_command = [
    #     '-v', 'error',
    #     '-show_entries', 'format=duration',
    #     '-of', 'default=noprint_wrappers=1:nokey=1',
    #     input_video_path
    # ]
    # result = run_ffprobe_cmd(duration_command)
    # total_duration = float(result.stdout.strip())
    video_info = get_video_info(input_video_path)
    duration_hms = video_info['duration_hms']
    # 计算需要截取的片段数量
    num_clips = int(duration_hms // interval)
    # 构建并执行命令
    for i in range(num_clips):
        start_time = i * interval
        clip_output_path = os.path.join(output_dir, f'clip_{i + 1:04d}.mp4')
        command = [
            '-i', input_video_path,  # 输入视频文件
            '-ss', str(start_time),  # 开始时间
            '-t', str(interval),  # 持续时间
            '-vsync', '0',  # 确保不跳过帧
            '-copyts',  # 复制时间戳
            '-avoid_negative_ts', 'make_zero',  # 避免负时间戳
            '-c:v', 'libx264',  # 重新编码视频流
            '-c:a', 'aac',  # 重新编码音频流
            clip_output_path  # 输出文件
        ]
        run_ffmpeg_cmd(command)


# 提取音频
def get_audio(video_path, output_path):
    command = [
        '-i', video_path,  # 输入文件
        '-q:a', '0',  # 音频质量（0是最好的）
        '-map', 'a',  # 只选择音频流
        output_path  # 输出文件
    ]
    run_ffmpeg_cmd(command)


# # 添加音频
def add_audio_to_video(video_path, audio_path, output_path):
    command = [
        '-i', video_path,  # 输入视频文件
        '-i', audio_path,  # 输入音频文件
        '-c:v', 'copy',  # 复制视频流，不重新编码
        '-c:a', 'aac',  # 使用AAC编码器编码音频
        '-map', '0:v:0',  # 映射第一个输入的第一个视频流
        '-map', '1:a:0',  # 映射第二个输入的第一个音频流
        '-shortest',  # 使输出文件长度与最短的输入文件相同
        output_path  # 输出文件
    ]
    run_ffmpeg_cmd(command)
    return output_path


def mix_audios_to_video(video_path, tts_path=None, bgm_path=None, bgm_volume=0.3, output_path=None):
    """
    将 TTS 语音和 BGM 混合后添加到视频

    Args:
        video_path: 输入视频路径
        tts_path: TTS 语音文件路径（可选）
        bgm_path: BGM 文件路径（可选）
        bgm_volume: BGM 音量 (0.0-1.0)，TTS 固定为 1.0
        output_path: 输出文件路径
    """
    if not output_path:
        output_path = video_path.replace(".mp4", "_mixed.mp4")

    if tts_path and bgm_path:
        # 两者都有：用 amix 混合 TTS + BGM
        command = [
            '-y',
            '-i', str(video_path),
            '-i', str(tts_path),
            '-i', str(bgm_path),
            '-filter_complex',
            f'[1:a]volume=1.0[tts];[2:a]volume={bgm_volume}[bgm];[tts][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]',
            '-map', '0:v:0',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            str(output_path)
        ]
    elif tts_path:
        # 只有 TTS
        return add_audio_to_video(video_path, tts_path, output_path)
    elif bgm_path:
        # 只有 BGM（按指定音量）
        command = [
            '-y',
            '-i', str(video_path),
            '-i', str(bgm_path),
            '-filter_complex',
            f'[1:a]volume={bgm_volume}[aout]',
            '-map', '0:v:0',
            '-map', '[aout]',
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            str(output_path)
        ]
    else:
        return video_path

    run_ffmpeg_cmd(command)
    return output_path


# 合并视频
def concatenate_videos_with_filter(video_paths, output_path):
    # 构建filter_complex选项
    filter_complex = f'concat=n={len(video_paths)}:v=1:a=1 [v] [a]'
    command = []
    for video in video_paths:
        command.extend(['-i', video])

    command.extend([
        '-filter_complex', filter_complex,
        '-map', '[v]',
        '-map', '[a]',
        '-c:v', 'libx264',  # 使用H.264编码器
        '-c:a', 'aac',  # 使用AAC编码器
        output_path  # 输出文件
    ])
    run_ffmpeg_cmd(command)
    return "视频合并成功，文件地址为：" + output_path


def add_subtitle(video_path, subtitle_content, subtitle_type,
                 fontname="楷体", fontsize=16, fontcolor="&Hffffff",
                 fontbordercolor="&H000000", subtitle_bottom=20
                 ):
    """添加字幕到视频文件
    Args:
        video_path:  视频url
        subtitle_content: 字幕内容
        subtitle_type: 字幕类型：硬字幕 如按字母
        font_name: 支持系统已安装的任何字体
        fontsize: 字体大小
        font_color: ASS格式颜色代码，默认白色，黑色
        subtitle_bottom: 底部边距像素值
    """
    cmd = ["-hide_banner",
           "-ignore_unknown",
           '-y',
           '-i',
           os.path.normpath(video_path)
           ]
    # 获取文件名称
    name = get_file_name_no_suffix(video_path)
    srt_file = f'{name}.srt'
    # 保存str文件
    with open(srt_file, "w", encoding="utf-8") as file:
        file.write(subtitle_content)
    if subtitle_type:
        # 软字幕
        cmd += [
            '-i', srt_file,
            '-c:v', 'copy' if Path(video_path).suffix.lower() == '.mp4' else 'libx264',
            '-c:s', 'mov_text',
            '-metadata:s:s:0', 'language=chi'  # 设置字幕语言，例如中文
        ]
    else:
        # 硬字幕
        ass_file = f'{name}.ass'
        # 字幕文件SRT转ASS
        str_to_ass(srt_file, ass_file)
        # 设置ass字体格式
        string_util.set_ass_font(ass_file, fontname, fontsize, fontcolor, fontbordercolor, subtitle_bottom)
        # FFmpeg 字幕滤镜需要转义路径中的特殊字符（冒号、反斜杠）
        # Windows 路径需要转义：C\:/path/to/file.ass
        escaped_ass_path = ass_file.replace('\\', '/').replace(':', '\\:')
        cmd += [
            '-c:v', 'libx264',
            '-vf', f"subtitles='{escaped_ass_path}'",
            '-crf', '13',
            '-preset', "slow"
        ]
    output_video = config.ROOT_DIR_WIN / config.UPLOAD_DIR / f'video_add_subtitle.mp4'
    cmd.append(output_video)
    run_ffmpeg_cmd(cmd)
    del_file(srt_file)
    del_file(ass_file)
    return f'video_add_subtitle.mp4'


# 字幕文件SRT转ASS
def str_to_ass(srt_file, ass_file):
    run_ffmpeg_cmd(['-hide_banner', '-ignore_unknown',
                    '-y',
                    '-i',
                    f'{srt_file}',
                    f'{ass_file}'])


# 分割视频
def cut_video(input_path, start_time, end_time=None, duration=None, output_suffix="(剪切)"):
    output_path = config.ROOT_DIR_WIN / "static/uploads" / f"{get_file_name_no_suffix(input_path)}{output_suffix}{get_file_suffix(input_path)}"
    command = [
        '-y',
        '-ss', start_time,
        '-i', str(input_path),
        '-an',  # 禁用音频
        '-c:v', 'libx264',
        '-vsync', 'cfr',  # 保证恒定帧率
        '-video_track_timescale', '1000',  # 关键：统一时间基为1/1000
        '-g', '60',  # 关键：设置GOP长度避免丢帧
        '-preset', 'fast',
        '-r', '30',  # 强制输出帧率为30
    ]
    if end_time:
        command.extend(['-to', end_time])
    elif duration:
        command.extend(['-t', duration])
    command.append(str(output_path))
    run_ffmpeg_cmd(command)
    return output_path


def cut_video_silence(input_path, start_time, end_time, output_suffix):
    """剪切视频并强制静音"""
    output_path = config.ROOT_DIR_WIN / "static/uploads" / f"{get_file_name_no_suffix(input_path)}{output_suffix}{get_file_suffix(input_path)}"
    command = [
        '-y',
        '-i', str(input_path),
        '-ss', start_time,
        '-an',  # 禁用音频
        '-c:v', 'libx264',
        '-vf',
        'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2,setpts=PTS-STARTPTS',
        # 关键修改：统一分辨率
        '-vsync', 'cfr',
        '-video_track_timescale', '1000',
        '-r', '30',
        '-preset', 'fast'
    ]
    if end_time:
        command.extend(['-to', end_time])
    elif duration:
        command.extend(['-t', duration])
    command.append(str(output_path))
    run_ffmpeg_cmd(command)
    return output_path


def concatenate_videos_with_transitions(clip_infos, output_path):
    logger.info("========================剪切生成中间文件=================================")
    intermediate_files = []
    # 总时长
    cut_total_duration = 0
    n = len(clip_infos)

    # 批量查询所有需要的视频（修复 N+1 查询问题）
    video_ids = [clip['id'] for clip in clip_infos]
    with get_db_context() as db:
        video_objs = db.query(VideoSource).filter(VideoSource.id.in_(video_ids)).all()
        video_dict = {v.id: _video_source_to_dict(v) for v in video_objs}

    # 检查是否所有视频都找到了
    missing_ids = set(video_ids) - set(video_dict.keys())
    if missing_ids:
        raise ValueError(f"Videos with ids {missing_ids} not found")

    for i in range(n):
        clip = clip_infos[i]
        start = clip['start_time']
        end = clip['end_time']
        if i > 0 and clip_infos[i - 1]['transition'] == 'dissolve':
            start = time_util.adjust_time(start, -0.5)
        if i < n - 1 and clip['transition'] == 'dissolve':
            end = time_util.adjust_time(end, +0.5)

        # 从预加载的字典中获取视频信息
        video_source = video_dict.get(clip['id'])
        if not video_source:
            raise ValueError(f"Video with id {clip['id']} not found")

        output_file = cut_video_silence(
            video_source["local_path"],
            str(start),
            end_time=str(end),
            output_suffix=f"({len(intermediate_files)})"
        )
        # duration 可能是字符串，需要转换为浮点数
        duration_val = float(video_source["duration"]) if video_source.get("duration") else 0
        cut_total_duration += duration_val
        intermediate_files.append(output_file)
    logger.info("视频合成前处理完成，开始合成...")
    inputs = []
    for file in intermediate_files:
        inputs.extend(['-i', str(file)])
    # 构建过滤器链（增强兼容性）
    filter_script = []
    # 步骤1：预处理（统一分辨率、时间基、帧率）
    for i in range(len(intermediate_files)):
        filter_script.append(
            f"[{i}:v]scale=1280:720:force_original_aspect_ratio=decrease,"
            f"pad=1280:720:(ow-iw)/2:(oh-ih)/2,"
            f"settb=AVTB,"  # 强制时间基为1/1000000
            f"fps=30,"  # 统一帧率为30
            f"setpts=PTS-STARTPTS,"  # 重置时间戳
            f"format=yuv420p[v{i}];"
        )
    # 步骤2：正确级联所有视频流
    current_stream = "v0"
    for i in range(len(intermediate_files) - 1):
        next_stream = f"v{i + 1}"
        filter_script.append(
            f"[{current_stream}][{next_stream}]"
            f"concat=n=2:v=1:a=0[out{i}];"
        )
        current_stream = f"out{i}"  # 更新当前流为输出
    # 计算总时长
    # cut_total_duration = sum(
    #     ffmpeg_util.get_video_duration(file) for file in intermediate_files
    # )
    # 步骤3：添加音频流和最终输出
    filter_script.append(
        f"aevalsrc=0:d={cut_total_duration}[aout];"
        f"[{current_stream}]format=yuv420p[vout]"
    )
    logger.info("开始视频合成...")
    # 构建完整命令（增加硬件加速支持）
    command = [
        '-y',
        '-hwaccel', 'auto',  # 启用硬件加速
        *inputs,
        '-filter_complex', ''.join(filter_script),
        '-map', '[vout]',
        '-map', '[aout]',
        '-c:v', 'h264_nvenc' if ffmpeg_util.check_nvidia() else 'libx264',  # 自动检测NVIDIA显卡
        '-preset', 'fast',
        '-profile:v', 'main',
        '-movflags', '+faststart',
        '-c:a', 'aac',
        '-b:a', '192k',
        '-shortest',
        str(output_path)
    ]
    run_ffmpeg_cmd(command)
    return "合并成功"


def compress_video_h265(
        input_path,
        output_path=None,
        crf=20,
        max_bitrate='8000k',
        audio_bitrate='64k',
        preset=None,
        use_gpu=True,
        gpu_accelerator=None
):
    """
    智能视频压缩函数 (自动选择GPU/CPU编码)
    参数:
    - input_path: 输入视频路径
    - output_path: 输出路径(可选)
    - crf: 质量因子(18-28, 默认23)
    - max_bitrate: 最大比特率(如 '1500k')
    - audio_bitrate: 音频比特率(如 '64k')
    - use_gpu: 是否启用GPU加速(默认True)
    - gpu_accelerator: 强制指定加速类型(可选: nvidia, amd, qsv, videotoolbox)
    """
    input_path = Path(input_path)
    output_path = input_path.parent / f"{input_path.stem}_h256.mp4"
    # 获取原始视频信息
    original_info = get_video_info(input_path)
    original_size = input_path.stat().st_size
    # 检查是否需要压缩
    if not ffmpeg_util.should_compress(original_info):
        return None
    # 智能调整压缩参数
    crf = ffmpeg_util.smart_crf_selection(original_info, default_crf=crf)
    max_bitrate = ffmpeg_util.smart_max_bitrate(original_info, default_bitrate=max_bitrate)
    # 构建基础命令
    command = ['-y',
               '-i',
               str(input_path)]
    # 自动检测GPU加速器
    if gpu_accelerator:
        accelerator = gpu_accelerator.lower()
    elif use_gpu:
        accelerator = ffmpeg_util.detect_gpu_accelerator()
    else:
        accelerator = 'cpu'
    command = ffmpeg_util.extend_accelerator(command, accelerator, preset, crf, audio_bitrate)
    command.append(str(output_path))
    # 执行命令
    try:
        logger.info(f"执行压缩命令: {' '.join(command)}")
        run_ffmpeg_cmd(command)
        # 检查压缩后文件大小
        if output_path.exists():
            compressed_size = output_path.stat().st_size
            compression_ratio = compressed_size / original_size
            logger.info(f"压缩成功! 原始大小: {original_size / (1024 * 1024):.2f}MB -> "
                        f"压缩后: {compressed_size / (1024 * 1024):.2f}MB (比例: {compression_ratio:.2%})")
            # 如果压缩后文件反而变大
            if compression_ratio >= 1.0:
                logger.warning("压缩后文件反而变大! 将删除压缩文件")
                output_path.unlink()
                output_path = input_path.parent / f"{input_path.stem}_y_h256.mp4"
                file_util.rename_file(input_path, output_path)
                return None
            # elif compression_ratio > 0.95:
            #     logger.warning("压缩效果不佳，文件大小几乎未减少")
            return output_path
        else:
            logger.error("压缩成功但输出文件不存在")
            return None
    except subprocess.CalledProcessError as e:
        # GPU失败自动回退到CPU
        if use_gpu and accelerator != 'cpu':
            logger.warning("GPU加速失败, 尝试CPU编码...")
            return compress_video_h265(
                input_path, output_path, crf, max_bitrate,
                audio_bitrate, preset, use_gpu=False
            )
        logger.error(f"压缩失败! 错误信息:\n{e.stderr}")
        return None
    except Exception as e:
        logger.error(f"压缩过程中发生异常: {e}")
        return None


def batch_compress_videos(
    input_dir,
    backup_dir,
    crf=20,
    max_bitrate='8000k',
    skip_existing=True,
    max_workers=None
):
    """
    批量压缩文件夹内所有视频（支持并发处理）

    参数:
    - input_dir: 输入文件夹路径
    - backup_dir: 原始视频备份目录
    - crf: 压缩质量因子 值越高压缩越多 (22-26)
    - max_bitrate: 限制最大比特率
    - skip_existing: 是否跳过已存在的压缩文件
    - max_workers: 最大并发工作线程数，None 表示根据 CPU 核心数自动确定
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import threading

    # 确定并发工作线程数
    if max_workers is None:
        import os
        # 默认使用 CPU 核心数，最多 4 个
        cpu_count = os.cpu_count() or 1
        max_workers = min(cpu_count, 4)

    logger.info(f"批量压缩任务启动，并发线程数: {max_workers}")

    # 确保备份目录存在
    backup_path = Path(backup_dir)
    backup_path.mkdir(parents=True, exist_ok=True)

    # 支持的视频扩展名
    video_extensions = ['.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.mpg', '.mpeg', '.ts', '.mts', '.m2ts']

    # 先获取所有视频文件列表
    all_video_files = []
    for file_path in Path(input_dir).rglob('*'):
        if file_path.is_file() and file_path.suffix.lower() in video_extensions:
            # 跳过已压缩文件（文件名包含_h256）
            if '_h256' in file_path.stem:
                continue
            all_video_files.append(file_path)

    # 统计信息（使用线程安全的方式）
    stats = {
        'total_files': len(all_video_files),
        'processed_files': 0,
        'skipped_files': 0,
        'compressed_files': 0,
        'failed_files': 0,
    }
    stats_lock = threading.Lock()

    def process_single_video(file_path):
        """处理单个视频压缩"""
        processed_files = 0
        skipped_files = 0
        compressed_files = 0
        failed_files = 0

        # 生成压缩后的路径
        output_path = file_path.parent / f"{file_path.stem}_h256.mp4"

        # 如果压缩文件已存在且需要跳过
        if skip_existing and output_path.exists():
            with stats_lock:
                stats['skipped_files'] += 1
                stats['processed_files'] += 1
            logger.info(f"跳过已存在: {file_path.name}")
            return 0, 1, 0, 0  # processed, skipped, compressed, failed

        try:
            # 压缩视频
            compressed_file = compress_video_h265(
                input_path=file_path,
                output_path=output_path,
                crf=crf,
                max_bitrate=max_bitrate
            )

            # 如果压缩成功且文件存在
            if compressed_file and compressed_file.exists():
                # 移动原始文件到备份目录
                backup_file = backup_path / file_path.name
                if not backup_file.exists():  # 避免覆盖
                    try:
                        shutil.move(str(file_path), str(backup_file))
                        logger.info(f"✓ {file_path.name} - 压缩成功，已备份")
                    except Exception as e:
                        logger.error(f"备份原始文件失败: {e}")
                else:
                    logger.info(f"✓ {file_path.name} - 压缩成功（备份已存在）")

                with stats_lock:
                    stats['compressed_files'] += 1
                    stats['processed_files'] += 1
                return 1, 0, 1, 0  # processed, skipped, compressed, failed
            else:
                logger.warning(f"✗ {file_path.name} - 压缩未成功完成")
                with stats_lock:
                    stats['failed_files'] += 1
                    stats['processed_files'] += 1
                return 1, 0, 0, 1
        except Exception as e:
            logger.error(f"✗ {file_path.name} - 处理失败: {e}")
            with stats_lock:
                stats['failed_files'] += 1
                stats['processed_files'] += 1
            return 1, 0, 0, 1

    start_time = time.time()

    # 使用线程池并发处理
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 提交所有任务
        future_to_file = {
            executor.submit(process_single_video, file_path): file_path
            for file_path in all_video_files
        }

        # 处理完成的任务
        for future in as_completed(future_to_file):
            file_path = future_to_file[future]
            try:
                future.result()
            except Exception as e:
                logger.error(f"任务异常 {file_path.name}: {e}")

    # 输出统计信息
    elapsed_time = time.time() - start_time
    logger.info(f"\n{'=' * 50}")
    logger.info(f"批量压缩完成! 用时: {elapsed_time / 60:.1f} 分钟")
    logger.info(f"总文件数: {stats['total_files']}")
    logger.info(f"跳过文件: {stats['skipped_files']}")
    logger.info(f"成功压缩: {stats['compressed_files']}")
    logger.info(f"失败文件: {stats['failed_files']}")
    logger.info(f"平均速度: {stats['total_files'] / (elapsed_time / 60):.1f} 文件/分钟")


def run_ffmpeg_cmd(cmd):
    # cmd执行ffmpeg命令
    # # ffmpeg
    # if sys.platform == 'win32':
    #     os.environ['PATH'] = ROOT_DIR + f';{ROOT_DIR}/ffmpeg;' + os.environ['PATH']
    #     if Path(ROOT_DIR + '/ffmpeg/ffmpeg.exe').is_file():
    #         FFMPEG_BIN = ROOT_DIR + '/ffmpeg/ffmpeg.exe'
    # else:
    #     os.environ['PATH'] = ROOT_DIR + f':{ROOT_DIR}/ffmpeg:' + os.environ['PATH']
    #     if Path(ROOT_DIR + '/ffmpeg/ffmpeg').is_file():
    #         FFMPEG_BIN = ROOT_DIR + '/ffmpeg/ffmpeg'
    try:
        command = [
            "ffmpeg"
        ]
        # 检查ffmpeg是否支持CUDA
        # if ffmpeg_util.check_cuda_support():
        #     command.extend(['-hwaccel', 'cuda'])
        command.extend(cmd)
        logger.debug(f"ffmpeg运行命令：{' '.join(str(c) for c in command)}")
        result = subprocess.run(command,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT,
                                text=True,
                                encoding="utf-8",
                                check=True,
                                creationflags=0 if sys.platform != 'win32' else subprocess.CREATE_NO_WINDOW
                                )
        return result
    except subprocess.CalledProcessError as e:
        logger.error("ffmpeg 命令执行失败")
        logger.error(f"Command: {e.cmd}")
        logger.error(f"Return code: {e.returncode}")
        logger.error(f"Output: {e.output}")


if __name__ == '__main__':
    import log_config
    # 开启日志配置
    log_config.log_run()
    # 总大小963GB
    SOURCE_FOLDER = "G:\\Walloaoer\\动漫\\番"
    # 备份文件夹
    BACKUP_FOLDER = "G:\\Walloaoer\\beifen"
    # 执行批量压缩
    logger.info("启动批量视频压缩任务")
    batch_compress_videos(
        input_dir=SOURCE_FOLDER,
        backup_dir=BACKUP_FOLDER
    )
    # get_video_info("G:\\Walloaoer\\A\\YM\\Who_h256.mp4")
    # 一些Python与ffmpeg音频处理的实用程序和命令:https://www.cnblogs.com/zhaoke271828/p/17007046.html
    input_video_path = "D:/abm/abm.mp4"
    output_video = "D:/output113.mp4"
    audio_output = "D:/abm.mp3"
    cover_image_path = "D:/opt/21.jpg"
    # output_video = "D:/abm/final"
    # input_subtitle_path = "D:/abm/abm.srt"
    # add_subtitle(input_video_path, input_subtitle_path, 50)

    # get_audio(input_video_path, audio_output)
    # get_video(input_video_path, output_video)
    # change_resolution(input_video_path, output_video, 640, 480)
    # speed_video(input_video_path, output_video, 1.5)
    # add_audio_to_video(input_video_path, audio_output, output_video)
    # adjust_audio_volume(input_video_path, output_video, 0.5)
    # convert_video_format(input_video_path, "D:/output111.avi")

    # 调用函数拼接视频
    # video_paths = [
    #     'D:/output111.mp4',
    #     'D:/output112.mp4'
    # ]
    # concatenate_videos_with_filter(video_paths, output_video)

    start_time = '00:00:10'
    # 从第10秒开始，持续20秒
    duration = '00:00:10'
    # 或者从第10秒开始，到第25秒结束
    end_time = '00:00:25'

    # 调用函数切割视频
    # cut_video(input_video_path, output_video, start_time, duration=duration)  # 使用持续时间
    # 或者
    # cut_video(input_video_path, output_video, start_time, end_time=end_time)  # 使用结束时间

    # set_video_cover(input_video_path, cover_image_path, output_video)
    time_in_hhmmss = '00:00:10'  # 提取第10秒的第一帧
    # extract_frame(input_video_path, "D:/21.jpg", time_in_hhmmss)
    # extract_frames(input_video_path, "D:/333", start_time, end_time)

    # video_to_gif(input_video_path, "D:/output.gif", start_time=start_time, duration=duration)
    # extract_video_clips(input_video_path, "D:/333")

    video_url = "D:\\sucai\\22.mp4"
    jpg_url = "D:\\video_sucai\\p1.jpg"
    # # 基本处理（只转格式）
    # print(process_video(video_url, output_format='avi'))
    #
    # # 加速处理+调整分辨率
    # print(process_video(video_url, speed_factor=1.5, width=1280, height=720))
    #
    # # 添加封面+剪切
    # print(process_video(video_url,
    #                     # cover_image=jpg_url,
    #                     start_time="00:01:00",
    #                     end_time="00:02:00"))

    # # 完整参数示例
    # print(process_video(video_url, output_format="mp4",
    #                     speed_factor=0.8,
    #                     volume_factor=2.0,
    #                     width=640, height=480,
    #                     start_time="00:00:30",
    #                     duration="00:01:30",
    #                     # cover_image="cover.png"
    #                     )
    #       )
    subtitle_content = """
1
00:00:00,000 --> 00:00:03,240
99推出LiveCC视频解说模型

2
00:00:03,240 --> 00:00:05,660
CC for Closed Caption
"""
    # Courier New
    # Impact
    # add_subtitle(video_url, subtitle_content, False,
    #              fontname="楷体", fontsize=16, fontcolor="&Hffffff",
    #              fontbordercolor="&H000000", subtitle_bottom=16)
