"""
漫剧视频合成服务
将分镜图片序列 + 音频 + BGM + 字幕合成为最终视频
"""
import os
import uuid
import logging
import tempfile
from typing import Dict, List, Any

from src import config

logger = logging.getLogger(__name__)


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ComicComposer:
    """将分镜面板合成为漫剧视频"""

    def compose(
        self,
        panels: List[Dict[str, Any]],
        bgm_config: Dict = None,
        project_id: int = 0,
    ) -> Dict[str, Any]:
        if not panels:
            return {"success": False, "error": "没有可用的分镜"}

        # 筛选有图片的分镜
        renderable = [p for p in panels if p.get("generated_image_path")]
        if not renderable:
            return {"success": False, "error": "没有已生成图片的分镜，请先生成分镜画面"}

        output_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
        os.makedirs(output_dir, exist_ok=True)

        # 1. 构建 concat demuxer 文件
        concat_path = os.path.join(output_dir, f"concat_{uuid.uuid4().hex[:8]}.txt")
        with open(concat_path, 'w', encoding='utf-8') as f:
            for panel in renderable:
                img = panel["generated_image_path"]
                if not os.path.isabs(img):
                    img = os.path.join(config.ROOT_DIR_WIN, img)
                dur = panel.get("duration", 3.0)
                f.write(f"file '{img}'\n")
                f.write(f"duration {dur}\n")
            # 最后一帧重复（concat demuxer 要求）
            last = renderable[-1]["generated_image_path"]
            if not os.path.isabs(last):
                last = os.path.join(config.ROOT_DIR_WIN, last)
            f.write(f"file '{last}'\n")

        # 2. FFmpeg 图片序列 → 视频
        video_name = f"comic_{project_id}_{uuid.uuid4().hex[:8]}.mp4"
        output_path = os.path.join(output_dir, video_name)

        from src.application.services import ffmpeg_adapter as ffmpeg

        try:
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_path,
                '-vf', 'scale=1280:720:force_original_aspect_ratio=decrease,pad=1280:720:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p',
                '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
                '-r', '24', '-pix_fmt', 'yuv420p', output_path,
            ])
        except Exception as e:
            return {"success": False, "error": f"视频合成失败: {e}"}
        finally:
            try:
                os.remove(concat_path)
            except OSError:
                pass

        # 3. 混合 BGM
        final_path = output_path
        if bgm_config and bgm_config.get("path"):
            final_path = self._mix_bgm(output_path, bgm_config, output_dir)

        web_path = f"static/projects/{project_id}/{os.path.basename(final_path)}"
        duration = ffmpeg.get_video_info(final_path).get("duration", 0) if hasattr(ffmpeg, 'get_video_info') else 0

        return {
            "success": True,
            "output_path": web_path,
            "web_path": web_path,
            "duration": float(duration),
        }

    def _mix_bgm(self, video_path: str, bgm_config: Dict, output_dir: str) -> str:
        bgm_path = bgm_config.get("path", "")
        volume = bgm_config.get("volume", 0.3)

        if not os.path.isabs(bgm_path):
            bgm_path = os.path.join(config.ROOT_DIR_WIN, bgm_path)
        if not os.path.exists(bgm_path):
            logger.warning(f"BGM 文件不存在: {bgm_path}")
            return video_path

        output = video_path.replace('.mp4', '_bgm.mp4')
        try:
            from src.application.services import ffmpeg_adapter as ffmpeg
            ffmpeg.run_ffmpeg_cmd([
                'ffmpeg', '-y', '-i', video_path, '-i', bgm_path,
                '-filter_complex', f'[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first[a]',
                '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-shortest', output,
            ])
            return output
        except Exception as e:
            logger.warning(f"BGM 混合失败: {e}")
            return video_path
