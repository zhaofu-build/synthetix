def seconds_to_hms(seconds):
    try:
        """将秒数转换为 HH:MM:SS 格式"""
        seconds = int(round(float(seconds)))  # 处理浮点数和四舍五入
        hours = seconds // 3600
        remainder = seconds % 3600
        minutes = remainder // 60
        seconds = remainder % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except (ValueError, TypeError):
        return "00:00:00"  # 异常时返回默认值


def parse_time(time_str):
    h, m, s_ms = time_str.split(':')
    s, ms = s_ms.split('.') if '.' in s_ms else (s_ms, '000')
    total_seconds = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000
    return total_seconds


def adjust_time(time_str, delta_seconds):
    total_seconds = parse_time(time_str)
    total_seconds += delta_seconds
    if total_seconds < 0:
        total_seconds = 0  # 防止时间变为负数
    return seconds_to_hms(total_seconds)
