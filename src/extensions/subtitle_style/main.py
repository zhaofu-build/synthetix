"""
字幕样式增强扩展

提供预设字幕风格模板，优化字幕生成效果。
"""
from src.agent.tool_registry import registry

PRESET_STYLES = {
    "variety": {
        "name": "综艺风格",
        "fontname": "Microsoft YaHei",
        "font_size": 28,
        "font_color": "&Hffffff",
        "outline_color": "&H000000",
        "outline_width": 3,
        "bold": True,
        "shadow": 1,
        "position": "bottom",
    },
    "news": {
        "name": "新闻风格",
        "fontname": "SimHei",
        "font_size": 22,
        "font_color": "&Hffffff",
        "outline_color": "&H000000",
        "outline_width": 2,
        "bold": True,
        "shadow": 0,
        "position": "bottom",
    },
    "movie": {
        "name": "电影风格",
        "fontname": "Microsoft YaHei",
        "font_size": 20,
        "font_color": "&Hffffff",
        "outline_color": "&H000000",
        "outline_width": 1,
        "bold": False,
        "shadow": 1,
        "position": "bottom",
    },
    "social": {
        "name": "社交媒体风格",
        "fontname": "Microsoft YaHei",
        "font_size": 26,
        "font_color": "&H00ffff",
        "outline_color": "&H000000",
        "outline_width": 2,
        "bold": True,
        "shadow": 0,
        "position": "center",
    },
    "default": {
        "name": "默认风格",
        "fontname": "Microsoft YaHei",
        "font_size": 24,
        "font_color": "&Hffffff",
        "outline_color": "&H000000",
        "outline_width": 2,
        "bold": False,
        "shadow": 1,
        "position": "bottom",
    },
}


def register_tools():
    """注册扩展工具"""

    @registry.register(
        name="subtitle_style_preset",
        description="获取字幕预设风格模板参数。返回指定风格的字体、颜色、描边等参数，可在 add_subtitle 工具中使用。",
        parameters={
            "style": {
                "type": "string",
                "description": "预设风格名称: variety(综艺), news(新闻), movie(电影), social(社交媒体), default(默认)",
            },
        },
        permission="read_only",
    )
    async def subtitle_style_preset(style: str = "default", **kwargs) -> dict:
        preset = PRESET_STYLES.get(style)
        if not preset:
            available = ", ".join(PRESET_STYLES.keys())
            return {
                "success": False,
                "error": f"未知预设风格: {style}，可用: {available}",
            }
        return {"success": True, "preset": style, "params": preset}
