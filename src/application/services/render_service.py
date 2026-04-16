"""
渲染服务

执行视频渲染和导出
"""
import os
import logging
from typing import Dict, List, Optional
import uuid
from pathlib import Path

from src import config
from src.application.services import ffmpeg_adapter as ffmpeg
from src.shared.models.timeline import Timeline, TimelineClip, Transition

logger = logging.getLogger(__name__)


class RenderService:
    """渲染服务"""

    def __init__(self):
        self.output_dir = config.UPLOAD_DIR
        os.makedirs(self.output_dir, exist_ok=True)

    def render_timeline(
        self,
        timeline: Timeline,
        audio_config: Dict = None
    ) -> str:
        """
        渲染时间线为视频

        Args:
            timeline: 时间线数据
            audio_config: 音频配置

        Returns:
            str: 输出文件路径
        """
        # 1. 构建剪辑信息
        clip_infos = self._build_clip_infos(timeline)

        if not clip_infos:
            raise ValueError("没有可渲染的视频片段")

        # 2. 合并视频（带转场）
        temp_video = self._merge_clips(clip_infos)

        # 3. 处理音频
        if audio_config:
            temp_video = self._add_audio(temp_video, audio_config)

        # 4. 生成最终输出
        output_path = os.path.join(
            self.output_dir,
            f"render_{timeline.project_id}_{os.getpid()}.mp4"
        )
        os.rename(temp_video, output_path)

        logger.info(f"渲染完成: {output_path}")
        return output_path

    def _build_clip_infos(self, timeline: Timeline) -> List[Dict]:
        """从时间线构建剪辑信息，供 ffmpeg 合并使用"""
        infos = []

        if not timeline.video_track or not timeline.video_track.clips:
            return infos

        clips = timeline.video_track.clips
        transitions = timeline.transitions or []

        for i, clip in enumerate(clips):
            # material_id 可能是数字ID或文件名，统一解析为数字ID
            video_id = self._resolve_material_id(clip.material_id)
            info = {
                "id": video_id,
                "start_time": self._format_time(clip.trim_start),
                "end_time": self._format_time(clip.trim_end),
                "transition": transitions[i].type if i < len(transitions) else "cut"
            }
            infos.append(info)

        return infos

    def _resolve_material_id(self, material_id) -> int:
        """将 material_id 解析为数字ID，支持文件名/模糊匹配"""
        # 已经是数字
        if isinstance(material_id, int):
            return material_id
        if isinstance(material_id, str) and material_id.isdigit():
            return int(material_id)

        # 按文件名/视频名查找
        from src.infrastructure.db.session import get_db_context
        from src.domain.entities.video_source import VideoSource

        try:
            with get_db_context() as db:
                # 精确匹配 video_name
                video = db.query(VideoSource).filter(
                    VideoSource.video_name == material_id
                ).first()
                if video:
                    return video.id

                # 模糊匹配
                video = db.query(VideoSource).filter(
                    VideoSource.video_name.contains(material_id)
                ).first()
                if video:
                    return video.id

                # 去掉扩展名再试
                name_no_ext = material_id.rsplit('.', 1)[0] if '.' in material_id else material_id
                video = db.query(VideoSource).filter(
                    VideoSource.video_name.contains(name_no_ext)
                ).first()
                if video:
                    return video.id
        except Exception as e:
            logger.error(f"解析素材ID失败: {e}")

        raise ValueError(f"找不到素材: {material_id}")

    def _merge_clips(self, clip_infos: List[Dict]) -> str:
        """合并视频片段（带转场）"""
        output_path = os.path.join(self.output_dir, f"temp_merge_{os.getpid()}.mp4")

        try:
            ffmpeg.concatenate_videos_with_transitions(clip_infos, output_path)
        except Exception as e:
            logger.error(f"视频合并失败: {e}")
            raise

        return output_path

    def _add_audio(self, video_path: str, audio_config: Dict) -> str:
        """
        处理音频：TTS 语音合成 + BGM 混合到视频

        audio_config 支持字段:
        - creative: str 文案内容（用于TTS）
        - speaker_id: int 音色ID
        - bgm_id: int BGM ID
        - bgm_volume: float BGM音量 (0.0-1.0)
        - bgm_path: str BGM文件路径（直接指定，优先于 bgm_id）
        - tts_path: str TTS文件路径（直接指定，优先于生成）
        """
        output_path = video_path.replace(".mp4", "_with_audio.mp4")

        # 获取 TTS 音频路径
        tts_path = audio_config.get("tts_path")
        if not tts_path and audio_config.get("creative") and audio_config.get("speaker_id"):
            tts_path = self._generate_tts(
                audio_config["creative"],
                audio_config["speaker_id"]
            )

        # 获取 BGM 音频路径
        bgm_path = audio_config.get("bgm_path")
        if not bgm_path and audio_config.get("bgm_id"):
            bgm_path = self._get_bgm_path(audio_config["bgm_id"])

        bgm_volume = audio_config.get("bgm_volume", 0.3)

        # 无音频可添加
        if not tts_path and not bgm_path:
            return video_path

        try:
            result = ffmpeg.mix_audios_to_video(
                video_path=video_path,
                tts_path=tts_path,
                bgm_path=bgm_path,
                bgm_volume=bgm_volume,
                output_path=output_path
            )
            return result
        except Exception as e:
            logger.error(f"添加音频失败: {e}")
            return video_path

    def _generate_tts(self, text: str, speaker_id: int) -> Optional[str]:
        """使用 TTS 合成语音"""
        from src.application.services.audio_service import AudioService
        from src.infrastructure.db.session import get_db_context
        try:
            with get_db_context() as db:
                audio_service = AudioService(db)
                result = audio_service.generate_fish_speech_tts(
                    text=text,
                    audio_source_id=speaker_id
                )
                tts_path = result.get("local_path")
            if tts_path and os.path.exists(tts_path):
                logger.info(f"TTS 生成成功: {tts_path}")
                return tts_path
            return None
        except Exception as e:
            logger.error(f"TTS 生成失败: {e}")
            return None

    def _get_bgm_path(self, bgm_id: int) -> Optional[str]:
        """根据 BGM ID 获取本地文件路径"""
        from src.infrastructure.db.session import get_db_context
        from src.domain.entities.bgm_item import BGMItem
        try:
            with get_db_context() as db:
                bgm = db.query(BGMItem).filter(BGMItem.id == bgm_id).first()
                if bgm and bgm.local_path and os.path.exists(bgm.local_path):
                    return bgm.local_path
        except Exception as e:
            logger.error(f"获取BGM路径失败: {e}")
        return None

    def _get_material_path(self, material_id) -> Optional[str]:
        """获取素材文件路径，支持数字ID和文件名"""
        from src.infrastructure.db.session import get_db_context
        from src.infrastructure.repositories import VideoRepository

        try:
            with get_db_context() as db:
                repo = VideoRepository(db)
                # 尝试按数字ID查找
                if isinstance(material_id, int) or (isinstance(material_id, str) and material_id.isdigit()):
                    video = repo.get_by_id(int(material_id))
                    if video and video.local_path:
                        return video.local_path
                # 尝试按文件名查找
                if isinstance(material_id, str):
                    video = repo.get_by_name(material_id)
                    if video and video.local_path:
                        return video.local_path
                    # 使用数据库 LIKE 查询代替全表扫描
                    from src.domain.entities.video_source import VideoSource
                    video = db.query(VideoSource).filter(
                        VideoSource.video_name.contains(material_id),
                        VideoSource.del_flag == 0
                    ).first()
                    if video and video.local_path:
                        return video.local_path
                return None
        except Exception as e:
            logger.error(f"获取素材路径失败: {e}")
            return None

    def _format_time(self, seconds: float) -> str:
        """秒数转 HH:MM:SS"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:05.2f}"

    def preview(
        self,
        timeline: Timeline,
        start: float = 0,
        end: float = None
    ) -> str:
        """
        生成预览视频（低分辨率，快速）

        Args:
            timeline: 时间线
            start: 开始时间
            end: 结束时间

        Returns:
            预览文件路径
        """
        # 限制预览时长
        if end is None:
            end = min(start + 30, timeline.duration)

        # 生成低分辨率预览
        # TODO: 实现预览渲染
        return self.render_timeline(timeline)

    def get_render_progress(self, task_id: str) -> Dict:
        """获取渲染进度"""
        # TODO: 实现进度追踪
        return {
            "task_id": task_id,
            "progress": 0,
            "status": "pending"
        }
