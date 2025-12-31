import json
import re


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
        print(f"Start: {sub['start']}s")
        print(f"End: {sub['end']}s")
        print(f"Content: {sub['content']}\n")


# 设置ass字体格式
def set_ass_font(ass_file, fontname, fontsize, fontcolor, fontbordercolor, subtitle_bottom):
    with open(ass_file, 'r+', encoding='utf-8') as f:
        content = f.read()

        # 使用正则表达式精准匹配样式行（包含Windows字体名空格）
        style_pattern = re.compile(r'^Style:\s*.*', flags=re.MULTILINE)
        new_style = (
            f"Style: Default,{fontname},{fontsize},"
            f"{fontcolor},&HFFFFFF,{fontbordercolor},&H0,0,0,0,0,"
            f"100,100,0,0,1,1,0,2,10,10,{subtitle_bottom},1"
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
