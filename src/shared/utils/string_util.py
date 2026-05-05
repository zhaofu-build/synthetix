import json
import re
import logging

logger = logging.getLogger(__name__)


def sanitize_title(title):
    # Only keep numbers, letters, Chinese characters, and spaces
    title = re.sub(r'[^\w\u4e00-\u9fff \d_-]', '', title)
    # Replace multiple spaces with a single space
    title = re.sub(r'\s+', ' ', title)
    return title


# 分析str字幕文件
def parse_srt(srt_text):
    subs = []
    lines = [line.strip() for line in srt_text.split('\n') if line.strip()]
    i = 0
    while i < len(lines):
        # 跳过序号行
        if lines[i].isdigit():
            i += 1
        else:
            # 处理可能的格式错误
            i += 1
            continue

        time_line = lines[i]
        i += 1
        content_lines = []
        # 收集内容行，直到下一个序号或结束
        while i < len(lines) and not lines[i].isdigit():
            content_lines.append(lines[i])
            i += 1
        content = ' '.join(content_lines)

        # 解析时间线
        start_time, end_time = time_line.split(' --> ')

        # # 转换时间为秒
        # def to_seconds(time_str):
        #     h, m, rest = time_str.split(':', 2)
        #     s, ms = rest.split(',', 1)
        #     return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
        #
        # start = to_seconds(start_time)
        # end = to_seconds(end_time)剪辑
        start = start_time
        end = end_time
        subs.append({'start': start, 'end': end, 'content': content})
    for sub in subs:
        logger.debug(f"字幕: Start={sub['start']}s, End={sub['end']}s, Content={sub['content'][:50]}...")


# 设置ass字体格式
def set_ass_font(ass_file, fontname, fontsize, fontcolor, fontbordercolor, subtitle_bottom,
                 bold=False, outline_width=1, shadow=0, alignment=2,
                 margin_l=10, margin_r=10, bg_color=None):
    """设置 ASS 字幕样式。

    Args:
        bold: 粗体
        outline_width: 描边宽度 0-6
        shadow: 阴影深度 0-4
        alignment: 位置 2=底部居中 5=上方居中 8=中间居中
        margin_l/margin_r: 左/右边距
        bg_color: 背景颜色 (ASS格式 &HBBGGRR)，有值时启用不透明背景
    """
    bold_val = -1 if bold else 0
    border_style = 3 if bg_color else 1  # 3=不透明底色, 1=描边+阴影
    back_colour = bg_color if bg_color else '&H0'

    with open(ass_file, 'r+', encoding='utf-8') as f:
        content = f.read()

        # 使用正则表达式精准匹配样式行（包含Windows字体名空格）
        style_pattern = re.compile(r'^Style:\s*.*', flags=re.MULTILINE)
        new_style = (
            f"Style: Default,{fontname},{fontsize},"
            f"{fontcolor},&HFFFFFF,{fontbordercolor},{back_colour},"
            f"{bold_val},0,0,0,"
            f"100,100,0,0,"
            f"{border_style},{outline_width},{shadow},{alignment},"
            f"{margin_l},{margin_r},{subtitle_bottom},1,0"
        )
        updated_content = re.sub(style_pattern, new_style, content, count=1)

        f.seek(0)
        f.write(updated_content)
        f.truncate()
    return ass_file


def get_bracket_json(clip_resp):
    # 获取字符串中[]之间的内容并转化为json
    # 步骤1：定位起始和结束位置
    start = clip_resp.find('[')  # 找到第一个 [ 的位置
    end = clip_resp.rfind(']') + 1  # 找到最后一个 ] 的位置并包含它
    if start == -1 or end == 0:
        raise ValueError("字符串中缺少有效的JSON数组边界 [ 或 ]")
    # 步骤2：提取 [ 和 ] 之间的内容
    json_str = clip_resp[start:end].strip()  # 去除首尾空白
    return json.loads(json_str)


def detect_prompt_language(text: str) -> str:
    # 判断语种
    has_japanese_kana = False
    has_chinese = False
    has_english = False

    for char in text:
        # 检测日文假名（平假名和片假名）
        if '\u3040' <= char <= '\u309F' or '\u30A0' <= char <= '\u30FF':
            has_japanese_kana = True
        # 检测汉字（包括中文和日文汉字）
        elif '\u4e00' <= char <= '\u9fff':
            has_chinese = True
        # 检测英文字母
        elif 'a' <= char.lower() <= 'z':
            has_english = True

    # 判断语种
    if has_japanese_kana:
        return '日英混合' if has_english else '日文'
    elif has_chinese:
        return '中英混合' if has_english else '中文'
    elif has_english:
        return '英文'
    else:
        # 默认返回英文（可根据需求调整）
        return '英文'


def remove_think_tags(text):
    # 正则匹配 <think>...</think> 标签及其中间内容（含换行符）
    pattern = r'<think>.*?</think>'
    # 使用 re.DOTALL 确保 . 匹配换行符，flags=re.DOTALL
    return re.sub(pattern, '', text, flags=re.DOTALL)


def clean_llm_json_response(text: str) -> str:
    """清理 LLM 返回的 JSON 文本，移除 markdown 代码块和 think 标签"""
    text = text.strip()
    # 移除 think 标签
    text = remove_think_tags(text).strip()
    # 移除 markdown 代码块包裹
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:])
    if text.endswith("```"):
        text = text.rsplit("```", 1)[0]
    return text.strip()


def safe_parse_llm_json(text: str):
    """安全解析 LLM 返回的 JSON，返回 None 表示解析失败"""
    cleaned = clean_llm_json_response(text)
    try:
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return None


# ==================== 安全相关工具函数 ====================

_TIME_FORMAT_PATTERN = re.compile(r'^\d{2}:\d{2}:\d{2}(\.\d+)?$')


def sanitize_time(time_str: str) -> str:
    """
    校验并清洗时间格式参数

    Args:
        time_str: 时间字符串，预期格式 HH:MM:SS

    Returns:
        校验后的时间字符串

    Raises:
        ValueError: 格式不合法
    """
    if not time_str:
        return time_str
    if not _TIME_FORMAT_PATTERN.match(time_str):
        raise ValueError(f"非法时间格式: {time_str}，需要 HH:MM:SS")
    return time_str


def sanitize_ffmpeg_string(value: str) -> str:
    """
    清洗 FFmpeg 字符串参数，移除命令注入字符

    Args:
        value: 待清洗的字符串

    Returns:
        清洗后的字符串
    """
    if not isinstance(value, str):
        return value
    return re.sub(r'[;&|`$]', '', value)
