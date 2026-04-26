"""
可观测性模块 — AI 调用监控 + 结构化日志辅助

记录每次 AI 调用的模型、Token 消耗、延迟、成功/失败。
提供统计 API 和成本估算。
"""
import json
import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

_METRICS_DIR = os.path.join(os.path.expanduser("~"), ".synthetix", "metrics")
_AI_CALL_LOG = os.path.join(_METRICS_DIR, "ai_calls.jsonl")


def _ensure_dir():
    os.makedirs(_METRICS_DIR, exist_ok=True)


def record_ai_call(
    service: str,
    model: str,
    tokens_in: int = 0,
    tokens_out: int = 0,
    latency_ms: float = 0,
    success: bool = True,
    error: str = "",
    project_id: int = None,
):
    """记录一次 AI 调用

    Args:
        service: LLM/TTS/ASR/VL/MUSIC
        model: 模型名称
        tokens_in: 输入 token 数
        tokens_out: 输出 token 数
        latency_ms: 耗时毫秒
        success: 是否成功
        error: 错误信息
        project_id: 项目 ID
    """
    _ensure_dir()
    entry = {
        "ts": time.time(),
        "service": service,
        "model": model,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "latency_ms": round(latency_ms, 1),
        "success": success,
        "error": error[:200] if error else "",
        "project_id": project_id,
    }
    try:
        with open(_AI_CALL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        logger.warning(f"AI 调用记录失败: {e}")


def get_ai_stats(hours: int = 24) -> Dict:
    """获取 AI 调用统计

    Returns:
        {
            "total_calls": int,
            "success_rate": float,
            "total_tokens_in": int,
            "total_tokens_out": int,
            "avg_latency_ms": float,
            "by_service": { service: {...} },
            "by_model": { model: {...} }
        }
    """
    if not os.path.exists(_AI_CALL_LOG):
        return {"total_calls": 0, "success_rate": 0, "total_tokens_in": 0,
                "total_tokens_out": 0, "avg_latency_ms": 0, "by_service": {}, "by_model": {}}

    cutoff = time.time() - hours * 3600
    calls = []
    try:
        with open(_AI_CALL_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("ts", 0) >= cutoff:
                        calls.append(entry)
                except json.JSONDecodeError:
                    continue
    except Exception:
        pass

    if not calls:
        return {"total_calls": 0, "success_rate": 0, "total_tokens_in": 0,
                "total_tokens_out": 0, "avg_latency_ms": 0, "by_service": {}, "by_model": {}}

    total = len(calls)
    successes = sum(1 for c in calls if c.get("success", True))
    total_in = sum(c.get("tokens_in", 0) for c in calls)
    total_out = sum(c.get("tokens_out", 0) for c in calls)
    latencies = [c.get("latency_ms", 0) for c in calls]
    avg_latency = sum(latencies) / len(latencies) if latencies else 0

    by_service = defaultdict(lambda: {"calls": 0, "successes": 0, "tokens": 0})
    by_model = defaultdict(lambda: {"calls": 0, "tokens": 0})

    for c in calls:
        svc = c.get("service", "unknown")
        by_service[svc]["calls"] += 1
        by_service[svc]["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)
        if c.get("success", True):
            by_service[svc]["successes"] += 1

        mdl = c.get("model", "unknown")
        by_model[mdl]["calls"] += 1
        by_model[mdl]["tokens"] += c.get("tokens_in", 0) + c.get("tokens_out", 0)

    return {
        "total_calls": total,
        "success_rate": round(successes / total * 100, 1) if total else 0,
        "total_tokens_in": total_in,
        "total_tokens_out": total_out,
        "avg_latency_ms": round(avg_latency, 1),
        "by_service": dict(by_service),
        "by_model": dict(by_model),
    }
