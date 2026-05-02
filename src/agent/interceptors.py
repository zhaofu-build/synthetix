"""
工具拦截器中间件

全局拦截器链，在工具执行前后自动处理横切关注点。
"""
import asyncio
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

def _infer_web_path(local_path: str) -> str:
    """根据文件实际路径推断正确的 web_path"""
    import os
    path = str(local_path).replace('\\', '/')
    # static/temp/{project_id}/xxx → /static/temp/{project_id}/xxx
    if '/static/temp/' in path:
        idx = path.index('/static/')
        return path[idx:]
    # static/source_videos/xxx → /static/source_videos/xxx
    if '/static/source_videos/' in path:
        idx = path.index('/static/')
        return path[idx:]
    # 其他路径回退
    return f"/static/source_videos/{os.path.basename(local_path)}"


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
    # 已有 video_id 或 temp_file_id 说明工具自己已注册，跳过
    if result.get("video_id") or result.get("temp_file_id"):
        return result
    try:
        from src.infrastructure.db.session import get_db_context
        from src.domain.entities.video_source import VideoSource
        import os
        if not os.path.exists(output_path):
            return result
        web_path = _infer_web_path(output_path)
        with get_db_context() as db:
            src = VideoSource(
                video_name=os.path.basename(output_path),
                local_path=output_path,
                web_path=web_path,
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


def auto_index_interceptor(result: Dict, tool_name: str) -> Dict:
    """视频素材注册后自动触发后台索引构建"""
    if not result.get("success"):
        return result
    material_id = result.get("material_id")
    if not material_id:
        return result
    try:
        from src.application.services.video_indexer import VideoIndexer
        indexer = VideoIndexer()
        asyncio.create_task(indexer.index_video_async(material_id))
        logger.info(f"[Interceptor] 后台索引已触发: video_id={material_id}")
    except Exception as e:
        logger.warning(f"[Interceptor] 后台索引触发失败: {e}")
    return result


def register_default_interceptors(registry):
    """注册默认拦截器"""
    registry.add_pre_interceptor(param_injection_interceptor)
    registry.add_pre_interceptor(cache_interceptor)
    registry.add_post_interceptor(material_registration_interceptor)
    registry.add_post_interceptor(auto_index_interceptor)
    registry.add_post_interceptor(execution_log_interceptor)
    registry.add_post_interceptor(ws_notification_interceptor)
    logger.info(f"已注册 {2} 个前置拦截器 + {4} 个后置拦截器")
