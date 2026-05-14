"""
多模态视觉语言服务（原 VL）

通过 core-nexus-ai /multimodal 接口进行图像/视频理解
"""
import logging
import os
from typing import Optional

from src.shared.utils.core_nexus_client import get_client
from src.shared.utils.config_manager import get as cfg_get

logger = logging.getLogger(__name__)

# 视频文件大小阈值：超过此值用关键帧方式，否则直接发视频 base64
_VIDEO_DIRECT_SIZE_LIMIT = 10 * 1024 * 1024  # 10 MB


def image_summary(tmp_path: str, prompt: Optional[str] = None) -> str:
    """
    图片内容总结

    Args:
        tmp_path: 图片文件路径
        prompt: 自定义提示词（可选）

    Returns:
        图片描述文本
    """
    if prompt is None:
        prompt = "用简练的语言描述这张图片"

    logger.info(f"🖼️ 图片理解 | 路径: {tmp_path}")

    try:
        client = get_client()
        vl_model = cfg_get("core_nexus.multimodal_model") or None

        # 本地文件转 base64（远程 VL API 如 DashScope 无法访问本地路径）
        image_input = tmp_path
        if tmp_path and not tmp_path.startswith(("http://", "https://", "data:")):
            image_input = _file_to_data_url(tmp_path)

        response = client.vl_generate(
            prompt=prompt,
            image=image_input,
            model=vl_model
        )
        logger.info(f"✅ 图片理解完成")
        return response

    except Exception as e:
        logger.error(f"❌ 图片理解失败: {e}")
        raise ValueError(f"图片理解失败: {e}")


def _file_to_data_url(file_path: str) -> str:
    """将本地文件转为 data URL 格式（base64）"""
    import base64
    import mimetypes

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "video/mp4"

    with open(file_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{encoded}"


def video_summary(tmp_path: str, prompt: Optional[str] = None, duration: Optional[float] = None, proxy_path: Optional[str] = None) -> str:
    """
    视频内容总结

    策略：
    1. 小文件 (<10MB): 转 base64 data URL 直接发送
    2. 大文件 (>=10MB) 或 base64 失败: 降级为关键帧方式

    Args:
        tmp_path: 视频文件路径
        prompt: 自定义提示词（可选）
        duration: 视频时长（秒），用于提示词中约束片段范围
        proxy_path: 代理文件路径（优先使用代理文件进行 VL 分析）

    Returns:
        视频描述文本
    """
    # 优先使用代理文件
    actual_path = proxy_path or tmp_path

    # 检查 VL 缓存（同文件+同 prompt → 复用）
    from src.shared.utils.result_cache import get_cached, set_cached
    vl_cache_kwargs = {"prompt_hash": hash(prompt or "")}
    cached = get_cached(actual_path, "vl", ttl=3600 * 4, **vl_cache_kwargs)
    if cached is not None:
        logger.info(f"[VL Cache] hit: {os.path.basename(actual_path)}")
        return cached

    if prompt is None:
        duration_hint = ""
        if duration and duration > 0:
            mins = int(duration) // 60
            secs = int(duration) % 60
            duration_str = f"{mins}分{secs}秒" if mins else f"{secs}秒"
            duration_hint = f"\n重要：该视频总时长为 {duration_str}（{duration:.1f}秒），所有片段的end时间不得超过 {duration:.1f}。"

        prompt = (
            "请分析这个视频，将画面内容连续片段合并为一段。" +
            duration_hint + "\n"
            "要求：\n"
            "1. start和end必须是视频的真实秒数，严格对齐视频实际时长\n"
            "2. 所有片段时间必须连续且覆盖完整时长\n"
            "3. desc简述该时间段的真实画面内容\n"
            "4. 严格按以下JSON格式输出，不要输出任何其他文字：\n"
            '{"segments":[{"start":0,"end":5,"desc":"画面描述"},{"start":5,"end":12,"desc":"画面描述"}]}'
        )

    logger.info(f"🎬 视频理解 | 路径: {actual_path}")

    try:
        client = get_client()
        vl_model = cfg_get("core_nexus.multimodal_model") or None

        # 小文件：转 base64 发送（远程 VL API 如 DashScope 不支持本地路径）
        file_size = os.path.getsize(actual_path) if os.path.exists(actual_path) else 0
        if file_size < _VIDEO_DIRECT_SIZE_LIMIT and not proxy_path:
            logger.info(f"📹 视频文件 ({file_size / 1024 / 1024:.1f}MB)，base64 发送")
            try:
                video_data = _file_to_data_url(actual_path)
                response = client.vl_generate(
                    prompt=prompt,
                    video=video_data,
                    model=vl_model
                )
                set_cached(actual_path, "vl", response, **vl_cache_kwargs)
                return response
            except Exception as e:
                logger.warning(f"base64 发送失败，降级为关键帧方式: {e}")

        # 大文件或 base64 失败：提取关键帧截图
        logger.info(f"🖼️ 提取关键帧进行分析")
        frames = _extract_keyframes(actual_path, duration)
        if not frames:
            raise ValueError("无法提取视频关键帧")

        # frames: [(data_url, timestamp), ...]
        frame_data_urls = [f[0] for f in frames]
        frame_times = [f[1] for f in frames]

        frame_prompt = prompt + (
            f"\n\n以下是视频的 {len(frames)} 个关键帧截图"
            f"（按时间顺序排列），请根据这些截图分析视频内容。"
        )

        # 尝试 images 数组方式
        try:
            response = client.vl_generate(
                prompt=frame_prompt,
                images=frame_data_urls,
                model=vl_model
            )
            logger.info(f"✅ 视频理解完成（关键帧模式，{len(frames)} 帧）")
            set_cached(actual_path, "vl", response, **vl_cache_kwargs)
            return response
        except Exception as e:
            logger.warning(f"images 数组方式失败: {e}，降级为逐帧分析")

        # images 失败：逐帧发送，单张 image 方式
        segments = []
        for i, (frame_url, t) in enumerate(frames):
            try:
                # 计算该帧对应的时间段
                next_t = frame_times[i + 1] if i + 1 < len(frame_times) else (duration or t + 5)
                start = frame_times[0] if i == 0 else (frame_times[i - 1] + t) / 2
                end = (t + next_t) / 2
                frame_prompt_single = (
                    f"这是视频第 {t:.1f} 秒的画面截图。"
                    f"请用简练语言描述这个时刻的画面内容（场景、人物动作、风格等），不要输出JSON。"
                )
                desc = client.vl_generate(
                    prompt=frame_prompt_single,
                    image=frame_url,
                    model=vl_model
                )
                segments.append({"start": round(start, 1), "end": round(end, 1), "desc": desc.strip()})
            except Exception as e:
                logger.warning(f"第 {i+1} 帧分析失败: {e}")

        if segments:
            import json
            response = json.dumps({"segments": segments}, ensure_ascii=False)
            set_cached(actual_path, "vl", response, **vl_cache_kwargs)
            return response
        raise ValueError("所有关键帧分析均失败")

    except Exception as e:
        logger.error(f"❌ 视频理解失败: {e}")
        raise ValueError(f"视频理解失败: {e}")


def _extract_keyframes(video_path: str, duration: Optional[float] = None, max_frames: int = 8) -> list:
    """
    从视频中均匀提取关键帧截图

    Args:
        video_path: 视频文件路径
        duration: 视频时长（秒），不提供则用 FFmpeg 获取
        max_frames: 最大提取帧数

    Returns:
        [(data_url, timestamp), ...] 列表
    """
    import tempfile
    from src.application.services import ffmpeg_adapter as ffmpeg

    # 获取视频时长
    if not duration or duration <= 0:
        info = ffmpeg.get_video_info(video_path)
        duration = info.get("duration", 0) if info else 0

    if duration <= 0:
        # 无法获取时长，至少提取一帧
        duration = 1

    # 计算提取帧数：短视频少提取，长视频多提取
    num_frames = min(max_frames, max(3, int(duration / 5)))
    if duration <= 10:
        num_frames = min(3, max(1, int(duration / 2)))

    frames = []
    tmp_dir = tempfile.mkdtemp(prefix="vl_frames_")

    try:
        for i in range(num_frames):
            # 均匀分布时间点
            t = (i + 0.5) * duration / num_frames
            t = min(t, duration - 0.1)
            if t < 0:
                t = 0
            out_path = os.path.join(tmp_dir, f"frame_{i:03d}.jpg")
            try:
                ffmpeg.run_ffmpeg_cmd([
                    '-y', '-ss', str(t), '-i', video_path,
                    '-vframes', '1', '-q:v', '2',
                    '-vf', 'scale=-2:480',
                    out_path
                ])
                if os.path.exists(out_path) and os.path.getsize(out_path) > 0:
                    frames.append((_file_to_data_url(out_path), t))
            except Exception as e:
                logger.warning(f"提取第 {i} 帧失败 (t={t:.1f}s): {e}")
    finally:
        # 清理临时文件
        import shutil
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass

    return frames


def generate_summary(messages: list) -> str:
    """
    通用生成函数，处理图像/视频并生成描述

    Args:
        messages: 消息列表，包含图片/视频和文本

    Returns:
        生成的描述文本
    """
    logger.info(f"🔄 VL 通用生成 | 消息数: {len(messages)}")

    try:
        client = get_client()
        vl_model = cfg_get("core_nexus.multimodal_model") or None

        # 从消息中提取 prompt 和图片
        prompt = ""
        images = []

        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", [])
                if isinstance(content, list):
                    for item in content:
                        if item.get("type") == "text":
                            prompt = item.get("text", "")
                        elif item.get("type") in ["image", "video"]:
                            img_path = item.get("image") or item.get("video")
                            if img_path:
                                images.append(img_path)
                elif isinstance(content, str):
                    prompt = content

        if not prompt:
            prompt = "请描述这个内容"

        response = client.vl_generate(
            prompt=prompt,
            images=images if images else None,
            messages=messages,
            model=vl_model
        )
        return response

    except Exception as e:
        logger.error(f"❌ VL 生成失败: {e}")
        raise ValueError(f"VL 生成失败: {e}")


if __name__ == '__main__':
    # 测试代码
    import sys

    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        result = image_summary(image_path, None)
        print(result)
    else:
        print("用法: python qwen_vl_adapter.py <image_path>")
