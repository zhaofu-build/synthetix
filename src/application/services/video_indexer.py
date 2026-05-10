"""
视频结构化索引服务

将视频离散化为镜头级语义单元，构建结构化索引用于快速检索和分析。
用本地 FFmpeg（场景检测+关键帧）+ ASR + 关键帧 VL 替代全视频 VL 调用。
"""
import asyncio
import logging
import os
from typing import Optional, List, Dict, Any

from src.shared.utils.result_cache import get_cached, set_cached

logger = logging.getLogger(__name__)


class VideoIndexer:
    """视频镜头索引器 — 将视频解构为结构化镜头索引"""

    def __init__(self):
        self._indexing_locks: Dict[int, asyncio.Lock] = {}

    # ── Public API ──

    def get_or_create_index(self, video_id: int) -> Optional[List[Dict[str, Any]]]:
        """获取已有索引，不存在则创建。返回镜头列表或 None。"""
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.shot_repository import ShotRepository

        with get_db_context() as db:
            repo = ShotRepository(db)
            if repo.has_complete_index(video_id):
                shots = repo.get_complete_shots(video_id)
                return [s.to_dict() for s in shots]

        # 无完整索引，触发构建
        success = self._run_index_pipeline(video_id)
        if not success:
            return None

        with get_db_context() as db:
            repo = ShotRepository(db)
            if repo.has_complete_index(video_id):
                shots = repo.get_complete_shots(video_id)
                return [s.to_dict() for s in shots]
        return None

    def build_structured_context(self, video_id: int, prompt: str = None, max_shots: int = 10) -> Optional[str]:
        """从镜头索引构建结构化文本上下文，供 LLM 分析使用。"""
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories import VideoRepository

        shots = self.get_or_create_index(video_id)
        if shots and max_shots:
            shots = shots[:max_shots]
        if not shots:
            return None

        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return None
            video_name = video.video_name
            duration = video.duration

        return self._build_context_text(
            {"video_name": video_name, "duration": duration},
            shots, prompt
        )

    async def index_video_async(self, video_id: int) -> bool:
        """异步执行视频索引（后台触发），内部在线程池中运行同步 pipeline。"""
        lock = self._indexing_locks.get(video_id)
        if lock and lock.locked():
            logger.info(f"[Indexer] video_id={video_id} 正在索引中，跳过")
            return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._run_index_pipeline, video_id)

    async def index_video_progressive(self, video_id: int):
        """渐进式索引，yield 进度事件。"""
        lock = self._indexing_locks.get(video_id)
        if lock and lock.locked():
            yield {"stage": "skipped", "message": "正在索引中", "progress": 0}
            return

        yield {"stage": "resolving", "message": "获取视频信息...", "progress": 0.1}
        video_info = self._resolve_video(video_id)
        if not video_info:
            yield {"stage": "error", "message": f"视频不存在: video_id={video_id}"}
            return

        video_path = video_info["local_path"]
        duration = video_info["duration"]

        yield {"stage": "detecting", "message": "检测场景切换...", "progress": 0.2}
        try:
            shots = self._detect_shots(video_path, duration)
        except Exception:
            shots = [{"start_time": 0.0, "end_time": duration}]

        yield {"stage": "keyframes", "message": f"提取关键帧 ({len(shots)} 个镜头)...", "progress": 0.4}
        keyframe_dir = os.path.join(os.path.dirname(video_path), f"index_keyframes_{video_id}")
        try:
            shots = self._extract_shot_keyframes(video_path, shots, keyframe_dir)
        except Exception:
            pass

        yield {"stage": "asr", "message": "语音转录中...", "progress": 0.6}
        try:
            segments = self._run_asr(video_path)
            shots = self._align_subtitles_to_shots(shots, segments, video_id=video_id)
        except Exception:
            pass

        yield {"stage": "vl", "message": "分析镜头...", "progress": 0.7}
        try:
            shots = self._analyze_keyframes(shots, max_shots=10, video_id=video_id)
        except Exception:
            pass

        success = self._persist_shots(video_id, shots)
        yield {
            "stage": "complete" if success else "error",
            "message": f"索引完成: {len(shots)} 个镜头" if success else "索引失败",
            "progress": 1.0,
            "shots_count": len(shots),
        }

    # ── Pipeline Steps ──

    def _resolve_video(self, video_id: int) -> Optional[Dict[str, Any]]:
        """从 DB 获取视频信息，验证文件存在。"""
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories import VideoRepository

        with get_db_context() as db:
            repo = VideoRepository(db)
            video = repo.get_by_id(video_id)
            if not video:
                return None
            local_path = video.local_path
            if not local_path or not os.path.exists(local_path):
                return None
            duration = float(video.duration) if video.duration else 0
            return {
                "video_id": video_id,
                "local_path": local_path,
                "duration": duration,
                "video_name": video.video_name or "",
            }

    def _detect_shots(self, video_path: str, duration: float) -> List[Dict[str, float]]:
        """调用 ffmpeg_adapter.detect_scene_changes() 检测场景切换，转为镜头列表。"""
        from src.application.services import ffmpeg_adapter as ffmpeg

        if duration <= 0:
            return [{"start_time": 0.0, "end_time": 0.0}]

        changes = ffmpeg.detect_scene_changes(video_path, threshold=0.3)
        if not changes:
            return [{"start_time": 0.0, "end_time": duration}]

        shots = []
        timestamps = [c["time"] for c in changes if 0 < c["time"] < duration]
        timestamps.sort()

        if not timestamps:
            return [{"start_time": 0.0, "end_time": duration}]

        prev = 0.0
        for ts in timestamps:
            shots.append({"start_time": round(prev, 3), "end_time": round(ts, 3)})
            prev = ts
        shots.append({"start_time": round(prev, 3), "end_time": round(duration, 3)})
        return shots

    def _extract_shot_keyframes(
        self, video_path: str, shots: List[Dict], output_dir: str
    ) -> List[Dict]:
        """为每个镜头提取 1-3 个关键帧。"""
        from src.application.services import ffmpeg_adapter as ffmpeg

        os.makedirs(output_dir, exist_ok=True)

        for i, shot in enumerate(shots):
            start = shot["start_time"]
            end = shot["end_time"]
            mid = (start + end) / 2
            keyframes = []

            # 短镜头取 1 帧，长镜头取 3 帧
            duration = end - start
            if duration <= 3:
                timestamps = [mid]
            else:
                third = duration / 3
                timestamps = [start + third, mid, start + 2 * third]

            for j, ts in enumerate(timestamps):
                fname = f"shot_{i:04d}_kf_{j}.jpg"
                out_path = os.path.join(output_dir, fname)
                if not os.path.exists(out_path):
                    try:
                        ffmpeg.extract_frame(
                            video_path,
                            f"{int(ts // 3600):02d}:{int((ts % 3600) // 60):02d}:{ts % 60:06.3f}",
                            out_path
                        )
                    except Exception as e:
                        logger.warning(f"[Indexer] 帧提取失败 shot={i} ts={ts:.2f}: {e}")
                        continue
                if os.path.exists(out_path):
                    keyframes.append({"path": out_path, "timestamp": round(ts, 3)})

            shot["keyframe_paths"] = keyframes

        return shots

    def _run_asr(self, video_path: str) -> List[Dict[str, Any]]:
        """调用 ASR 获取转录 segments [{start, end, text}]。"""
        from src.shared.utils.core_nexus_client import get_client
        from src.shared.utils.config_manager import get as cfg_get

        # 检查缓存
        cached = get_cached(video_path, "asr_raw", ttl=3600 * 2)
        if cached is not None:
            return cached

        try:
            client = get_client()
            asr_model = cfg_get("core_nexus.asr_model") or None
            result = client.asr_transcribe(audio=video_path, language="zh", model=asr_model)
            segments = result.get("segments", [])

            if not segments and result.get("text"):
                segments = [{"start": 0, "end": 0, "text": result["text"]}]

            parsed = [{"start": s.get("start", 0), "end": s.get("end", 0), "text": s.get("text", "").strip()}
                      for s in segments if s.get("text", "").strip()]

            set_cached(video_path, "asr_raw", parsed)
            return parsed

        except Exception as e:
            logger.warning(f"[Indexer] ASR 转录失败: {e}")
            return []

    def _align_subtitles_to_shots(
        self, shots: List[Dict], segments: List[Dict], video_id: int = None
    ) -> List[Dict]:
        """将 ASR segments 按时间重叠对齐到镜头。"""
        if not segments:
            return shots

        for shot in shots:
            # 镜头级字幕缓存
            si = shot.get("shot_index", 0)
            if video_id is not None:
                from src.shared.utils.result_cache import get_shot_cached, set_shot_cached
                shot_sub = get_shot_cached(video_id, si, "subtitle")
                if shot_sub is not None:
                    shot["subtitle_text"] = shot_sub
                    continue

            s_start = shot["start_time"]
            s_end = shot["end_time"]
            texts = []
            for seg in segments:
                seg_start = seg["start"]
                seg_end = seg["end"]
                # 重叠判断
                if seg_end <= s_start or seg_start >= s_end:
                    continue
                overlap = min(seg_end, s_end) - max(seg_start, s_start)
                seg_dur = seg_end - seg_start
                # 超过 50% 重叠则归入此镜头
                if seg_dur <= 0 or overlap / seg_dur > 0.5:
                    texts.append(seg["text"])
            shot["subtitle_text"] = " ".join(texts).strip() or None
            # 镜头级字幕缓存保存
            if video_id is not None and shot.get("subtitle_text"):
                from src.shared.utils.result_cache import set_shot_cached
                set_shot_cached(video_id, si, "subtitle", shot["subtitle_text"])

        return shots

    def _analyze_keyframes(
        self, shots: List[Dict], max_shots: int = 10, video_id: int = None
    ) -> List[Dict]:
        """对关键帧图像调用 image_summary 进行 VL 分析（限制调用次数）。"""
        from src.application.services import qwen_vl_adapter

        analyzed = 0
        for shot in shots:
            if analyzed >= max_shots:
                break
            kfs = shot.get("keyframe_paths", [])
            if not kfs:
                continue
            # 取中间帧作为代表
            mid_kf = kfs[len(kfs) // 2]
            kf_path = mid_kf["path"]
            if not os.path.exists(kf_path):
                continue

            # 检查镜头级缓存（优先于文件级缓存）
            si = shot.get("shot_index", 0)
            if video_id is not None:
                from src.shared.utils.result_cache import get_shot_cached, set_shot_cached
                shot_vl = get_shot_cached(video_id, si, "vl_desc")
                if shot_vl is not None:
                    shot["description"] = shot_vl
                    analyzed += 1
                    continue

            # 检查文件级缓存
            cached = get_cached(kf_path, "vl_image", ttl=3600 * 4)
            if cached is not None:
                shot["description"] = cached
                analyzed += 1
                continue

            try:
                desc = qwen_vl_adapter.image_summary(
                    tmp_path=kf_path,
                    prompt="分析这个画面，输出两行：\n1. 镜头类型（从 closeup/medium/wide/unknown 中选择一个）\n2. 一句话描述场景、人物、动作和氛围\n格式：类型: xxx\n描述: xxx"
                )
                if desc:
                    parsed = self._parse_vl_result(desc)
                    shot["description"] = parsed["description"]
                    shot["shot_type"] = parsed["shot_type"]
                    set_cached(kf_path, "vl_image", desc)
                    # 保存镜头级缓存
                    if video_id is not None:
                        from src.shared.utils.result_cache import set_shot_cached
                        set_shot_cached(video_id, si, "vl_desc", desc)
                        set_shot_cached(video_id, si, "shot_type", parsed["shot_type"])
                analyzed += 1
            except Exception as e:
                logger.warning(f"[Indexer] 关键帧 VL 分析失败: {e}")

        return shots

    def _parse_vl_result(self, text: str) -> Dict[str, str]:
        """解析 VL 结果，提取 shot_type 和 description"""
        result = {"shot_type": "unknown", "description": text}
        if not text:
            return result
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.startswith("类型:") or line.startswith("类型："):
                type_str = line.split(":", 1)[-1].strip().split("：", 1)[-1].strip().lower()
                if type_str in ("closeup", "medium", "wide", "unknown"):
                    result["shot_type"] = type_str
            elif line.startswith("描述:") or line.startswith("描述："):
                result["description"] = line.split(":", 1)[-1].strip().split("：", 1)[-1].strip()
        return result

    def _build_context_text(
        self, video_info: Dict, shots: List[Dict], prompt: str = None
    ) -> str:
        """将镜头元数据 + 字幕 + 关键帧描述组合为结构化文本。"""
        lines = [
            f"视频: {video_info.get('video_name', '未知')}",
            f"时长: {video_info.get('duration', 0)}秒",
            f"共 {len(shots)} 个镜头",
            "",
        ]

        for shot in shots:
            idx = shot.get("shot_index", 0)
            start = shot.get("start_time", 0)
            end = shot.get("end_time", 0)
            duration = round(end - start, 1)
            lines.append(f"--- 镜头 {idx + 1} [{start:.1f}s - {end:.1f}s] ({duration:.1f}s) ---")

            desc = shot.get("description")
            if desc:
                lines.append(f"画面: {desc}")

            sub = shot.get("subtitle_text")
            if sub:
                lines.append(f"台词: {sub}")

            lines.append("")

        return "\n".join(lines)

    def _persist_shots(self, video_id: int, shots: List[Dict]) -> bool:
        """将镜头数据持久化到 video_shots 表。"""
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories.shot_repository import ShotRepository
        from src.domain.entities.video_shot import VideoShot

        try:
            with get_db_context(commit=True) as db:
                repo = ShotRepository(db)
                repo.delete_by_video_id(video_id)

                for i, shot in enumerate(shots):
                    s = VideoShot(
                        video_id=video_id,
                        shot_index=i,
                        scene_group=i,
                        start_time=shot.get("start_time", 0),
                        end_time=shot.get("end_time", 0),
                        keyframe_paths=shot.get("keyframe_paths", []),
                        subtitle_text=shot.get("subtitle_text"),
                        description=shot.get("description"),
                        shot_type=shot.get("shot_type", "unknown"),
                        index_status="complete",
                    )
                    db.add(s)
                db.commit()
            return True
        except Exception as e:
            logger.error(f"[Indexer] 持久化镜头失败: {e}")
            return False

    def _run_index_pipeline(self, video_id: int) -> bool:
        """完整的索引流水线。"""
        from src import config

        # 1. 获取视频信息
        video_info = self._resolve_video(video_id)
        if not video_info:
            logger.warning(f"[Indexer] 视频不存在或文件缺失: video_id={video_id}")
            return False

        video_path = video_info["local_path"]
        duration = video_info["duration"]

        logger.info(f"[Indexer] 开始索引 video_id={video_id} duration={duration:.1f}s")

        # 2. 场景检测 → 镜头列表
        try:
            shots = self._detect_shots(video_path, duration)
        except Exception as e:
            logger.error(f"[Indexer] 场景检测失败: {e}")
            shots = [{"start_time": 0.0, "end_time": duration}]

        if not shots:
            shots = [{"start_time": 0.0, "end_time": duration}]

        # 3. 关键帧提取
        keyframe_dir = os.path.join(
            os.path.dirname(video_path), f"index_keyframes_{video_id}"
        )
        try:
            shots = self._extract_shot_keyframes(video_path, shots, keyframe_dir)
        except Exception as e:
            logger.warning(f"[Indexer] 关键帧提取失败（降级继续）: {e}")

        # 4. ASR + 字幕对齐
        try:
            segments = self._run_asr(video_path)
            shots = self._align_subtitles_to_shots(shots, segments, video_id=video_id)
        except Exception as e:
            logger.warning(f"[Indexer] ASR 失败（降级继续）: {e}")

        # 5. 关键帧 VL 分析（限制调用次数）
        try:
            shots = self._analyze_keyframes(shots, max_shots=10, video_id=video_id)
        except Exception as e:
            logger.warning(f"[Indexer] 关键帧 VL 失败（降级继续）: {e}")

        # 6. 持久化
        success = self._persist_shots(video_id, shots)
        if success:
            logger.info(f"[Indexer] 索引完成 video_id={video_id} shots={len(shots)}")
        return success
