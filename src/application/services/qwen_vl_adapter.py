"""
VL 视觉语言服务

通过 core-nexus-ai API 进行图像/视频理解
"""
import logging
from typing import Optional

from src.shared.utils.core_nexus_client import get_client
from src.shared.utils.config_manager import get as cfg_get

logger = logging.getLogger(__name__)


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
        vl_model = cfg_get("core_nexus.vl_model") or None
        # 本地文件路径转为 data URL
        if tmp_path and not tmp_path.startswith(("http://", "https://", "data:")):
            image_data = _file_to_data_url(tmp_path)
        else:
            image_data = tmp_path
        response = client.vl_generate(
            prompt=prompt,
            image=image_data,
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


def video_summary(tmp_path: str, prompt: Optional[str] = None, duration: Optional[float] = None) -> str:
    """
    视频内容总结

    Args:
        tmp_path: 视频文件路径
        prompt: 自定义提示词（可选）
        duration: 视频时长（秒），用于提示词中约束片段范围

    Returns:
        视频描述文本
    """
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

    logger.info(f"🎬 视频理解 | 路径: {tmp_path}")

    try:
        client = get_client()
        vl_model = cfg_get("core_nexus.vl_model") or None
        video_data = _file_to_data_url(tmp_path)
        response = client.vl_generate(
            prompt=prompt,
            video=video_data,
            model=vl_model
        )
        logger.info(f"✅ 视频理解完成")
        return response

    except Exception as e:
        logger.error(f"❌ 视频理解失败: {e}")
        raise ValueError(f"视频理解失败: {e}")


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
        vl_model = cfg_get("core_nexus.vl_model") or None

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
