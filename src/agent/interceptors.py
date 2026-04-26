"""
工具拦截器中间件

全局拦截器链，在工具执行前后自动处理横切关注点。
"""
import logging
import time
from typing import Dict, Callable

logger = logging.getLogger(__name__)


# ── 前置拦截器 ──

def param_injection_interceptor(params: Dict, tool_name: str) -> Dict:
    """自动注入通用参数（时间戳格式化等）"""
    if "start_time" in params and isinstance(params["start_time"], (int, float)):
        s = int(params["start_time"])
        params["start_time"] = f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    if "end_time" in params and isinstance(params["end_time"], (int, float)):
        s = int(params["end_time"])
        params["end_time"] = f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"
    return params


def cache_interceptor(params: Dict, tool_name: str) -> Dict:
    """对重复的只读查询返回缓存标记（实际缓存由各工具函数内部处理）"""
    # Cache logic is handled inside each tool function via result_cache module
    return params


# ── 后置拦截器 ──

def material_registration_interceptor(result: Dict, tool_name: str) -> Dict:
    """剪辑类工具产生的视频自动注册为素材"""
    if not result.get("success"):
        return result
    output_path = result.get("output_path") or result.get("web_url")
    if not output_path or not isinstance(output_path, str):
        return result
    # Only register for tools that produce video files
    video_tools = {"cut_video", "merge_videos", "smart_clip", "compress_video",
                   "change_speed", "convert_format", "split_video", "add_subtitle"}
    if tool_name not in video_tools:
        return result
    if result.get("_material_registered"):
        return result
    try:
        from src.infrastructure.db.session import get_db_context
        from src.domain.entities.video_source import VideoSource
        import os
        if not os.path.exists(output_path):
            return result
        with get_db_context() as db:
            src = VideoSource(
                video_name=os.path.basename(output_path),
                local_path=output_path,
                web_path=f"/static/uploads/{os.path.basename(output_path)}",
                video_type=1,
            )
            db.add(src)
            db.commit()
            result["material_id"] = src.id
            result["_material_registered"] = True
            logger.info(f"[Interceptor] 素材入库: {output_path} → ID {src.id}")
    except Exception as e:
        logger.warning(f"[Interceptor] 素材入库失败: {e}")
    return result


def ws_notification_interceptor(result: Dict, tool_name: str) -> Dict:
    """向 WebSocket 推送工具执行结果"""
    # WS notification is handled by the SSE stream in react_agent
    return result


def execution_log_interceptor(result: Dict, tool_name: str) -> Dict:
    """记录工具执行结果摘要"""
    success = result.get("success", True)
    if not success:
        error = result.get("error", "未知错误")
        logger.info(f"[ToolLog] {tool_name} FAILED: {error[:100]}")
    return result


def register_default_interceptors(registry):
    """注册默认拦截器"""
    registry.add_pre_interceptor(param_injection_interceptor)
    registry.add_pre_interceptor(cache_interceptor)
    registry.add_post_interceptor(material_registration_interceptor)
    registry.add_post_interceptor(execution_log_interceptor)
    registry.add_post_interceptor(ws_notification_interceptor)
    logger.info(f"已注册 {2} 个前置拦截器 + {3} 个后置拦截器")
