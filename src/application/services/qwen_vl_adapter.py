"""
VL 视觉语言服务

通过 core-nexus-ai API 进行图像/视频理解
"""
import logging
from typing import Optional

from src.shared.utils.core_nexus_client import get_client

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
        response = client.vl_generate(
            prompt=prompt,
            image=tmp_path
        )
        logger.info(f"✅ 图片理解完成")
        return response

    except Exception as e:
        logger.error(f"❌ 图片理解失败: {e}")
        raise ValueError(f"图片理解失败: {e}")


def video_summary(tmp_path: str, prompt: Optional[str] = None) -> str:
    """
    视频内容总结

    Args:
        tmp_path: 视频文件路径
        prompt: 自定义提示词（可选）

    Returns:
        视频描述文本
    """
    if prompt is None:
        prompt = "用简练的语言描述这个视频，总结成一句话"

    logger.info(f"🎬 视频理解 | 路径: {tmp_path}")

    try:
        client = get_client()
        response = client.vl_generate(
            prompt=prompt,
            video=tmp_path
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
            messages=messages
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
