"""
视频质量检测服务

检测跳切、爆音、黑屏、时长合规等常见问题
"""
import json
import logging
import os
import subprocess
import sys
from typing import Dict, List, Any, Optional

from src.shared.utils import time_util

logger = logging.getLogger(__name__)


def _run_ffprobe(input_path: str, args: list) -> Optional[dict]:
    cmd = ["ffprobe", "-v", "error"] + args + ["-of", "json", str(input_path)]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True, timeout=30,
            creationflags=0 if sys.platform != "win32" else subprocess.CREATE_NO_WINDOW,
        )
        return json.loads(result.stdout)
    except Exception as e:
        logger.warning(f"ffprobe failed for {input_path}: {e}")
        return None


def check_black_frames(input_path: str, threshold: float = 0.02, duration_min: float = 0.5) -> List[Dict]:
    """检测黑屏片段

    Returns: [{"start": float, "end": float, "duration": float}]
    """
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vf", f"blackdetect=d={duration_min}:pic_th={threshold}",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=0 if sys.platform != "win32" else subprocess.CREATE_NO_WINDOW,
        )
        blacks = []
        for line in result.stderr.splitlines():
            if "blackdetect" in line and "black_start" in line:
                parts = {}
                for token in line.split():
                    if "=" in token:
                        k, v = token.split("=", 1)
                        try:
                            parts[k] = float(v)
                        except ValueError:
                            pass
                if "black_start" in parts and "black_end" in parts:
                    blacks.append({
                        "start": round(parts["black_start"], 2),
                        "end": round(parts["black_end"], 2),
                        "duration": round(parts.get("black_duration", parts["black_end"] - parts["black_start"]), 2),
                    })
        return blacks
    except Exception as e:
        logger.warning(f"黑屏检测失败: {e}")
        return []


def check_audio_levels(input_path: str, db_threshold: float = -2.0) -> Dict[str, Any]:
    """检测爆音（音频电平过高）

    Returns: {"peak_db": float, "is_clipping": bool, "details": str}
    """
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-af", f"volumedetect",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=120,
            creationflags=0 if sys.platform != "win32" else subprocess.CREATE_NO_WINDOW,
        )
        max_volume = None
        mean_volume = None
        for line in result.stderr.splitlines():
            if "max_volume" in line:
                try:
                    max_volume = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass
            if "mean_volume" in line:
                try:
                    mean_volume = float(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError):
                    pass

        is_clipping = max_volume is not None and max_volume >= db_threshold
        return {
            "peak_db": max_volume,
            "mean_db": mean_volume,
            "is_clipping": is_clipping,
            "details": f"峰值 {max_volume}dB, 均值 {mean_volume}dB" if max_volume is not None else "无法检测",
        }
    except Exception as e:
        return {"peak_db": None, "mean_db": None, "is_clipping": False, "details": f"检测失败: {e}"}


def check_scene_cuts(input_path: str, threshold: float = 0.3) -> List[float]:
    """检测场景切换点（跳切检测）

    Returns: 切换时间点列表 [t1, t2, ...]
    """
    cmd = [
        "ffmpeg", "-i", str(input_path),
        "-vf", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-"
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=180,
            creationflags=0 if sys.platform != "win32" else subprocess.CREATE_NO_WINDOW,
        )
        cuts = []
        for line in result.stderr.splitlines():
            if "showinfo" in line and "pts_time" in line:
                try:
                    pts = line.split("pts_time:")[1].split()[0].rstrip(",")
                    cuts.append(round(float(pts), 2))
                except (ValueError, IndexError):
                    pass
        return cuts
    except Exception as e:
        logger.warning(f"场景切换检测失败: {e}")
        return []


def check_duration_compliance(clips: List[Dict], target_duration: float = None, tolerance: float = 2.0) -> Dict[str, Any]:
    """检查片段时长合规性

    Returns: {"total": float, "target": float, "compliant": bool, "gaps": [...]}
    """
    if not clips:
        return {"total": 0, "target": target_duration, "compliant": False, "gaps": ["无片段"]}

    total = sum(
        time_util.parse_time(clip.get("end_time", "00:00:00")) -
        time_util.parse_time(clip.get("start_time", "00:00:00"))
        for clip in clips
    )
    issues = []
    if target_duration and abs(total - target_duration) > tolerance:
        issues.append(f"总时长 {total:.1f}s 与目标 {target_duration}s 偏差超过 {tolerance}s")

    # Check for overlapping clips
    sorted_clips = sorted(clips, key=lambda c: time_util.parse_time(c.get("start_time", "00:00:00")))
    for i in range(1, len(sorted_clips)):
        prev_end = time_util.parse_time(sorted_clips[i - 1].get("end_time", "00:00:00"))
        curr_start = time_util.parse_time(sorted_clips[i].get("start_time", "00:00:00"))
        if curr_start < prev_end:
            issues.append(f"片段 {i} 与片段 {i + 1} 存在重叠")

    return {
        "total": round(total, 1),
        "target": target_duration,
        "compliant": len(issues) == 0,
        "gaps": issues,
    }


def run_quality_check(
    video_path: str = None,
    clips: List[Dict] = None,
    target_duration: float = None,
) -> Dict[str, Any]:
    """执行完整质量检测管线

    Args:
        video_path: 视频文件路径（用于黑屏/爆音检测）
        clips: 片段列表（用于时长合规检测）
        target_duration: 目标时长

    Returns:
        {"score": int, "issues": [...], "details": {...}}
    """
    issues = []
    details = {}
    score = 100

    # 1. 黑屏检测
    if video_path and os.path.exists(video_path):
        blacks = check_black_frames(video_path)
        details["black_frames"] = blacks
        if blacks:
            score -= min(len(blacks) * 5, 30)
            issues.append({"type": "black_frames", "severity": "warning", "count": len(blacks),
                           "message": f"检测到 {len(blacks)} 段黑屏"})

    # 2. 爆音检测
    if video_path and os.path.exists(video_path):
        audio = check_audio_levels(video_path)
        details["audio_levels"] = audio
        if audio.get("is_clipping"):
            score -= 15
            issues.append({"type": "audio_clipping", "severity": "error",
                           "message": f"音频爆音，峰值 {audio['peak_db']}dB"})

    # 3. 时长合规
    if clips:
        duration_check = check_duration_compliance(clips, target_duration)
        details["duration_compliance"] = duration_check
        if not duration_check["compliant"]:
            score -= 10
            for gap in duration_check["gaps"]:
                issues.append({"type": "duration_mismatch", "severity": "warning", "message": gap})

    # 4. 跳切检测
    if video_path and os.path.exists(video_path):
        cuts = check_scene_cuts(video_path)
        details["scene_cuts"] = len(cuts)
        if len(cuts) > 50:
            score -= 10
            issues.append({"type": "excessive_cuts", "severity": "info",
                           "message": f"检测到 {len(cuts)} 个场景切换点，可能过多"})

    score = max(0, score)
    severity_order = {"error": 0, "warning": 1, "info": 2}
    issues.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 2))

    return {
        "score": score,
        "issues": issues,
        "details": details,
        "summary": f"质量评分: {score}/100, {len(issues)} 个问题" + (f" ({sum(1 for i in issues if i['severity'] == 'error')} 严重)" if any(i['severity'] == 'error' for i in issues) else ""),
    }
