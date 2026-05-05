"""
漫剧视频合成服务
将分镜面板合成为完整视频：Ken Burns 效果 + 转场 + 配音 + BGM + 字幕
"""
import os
import uuid
import logging
import tempfile
from typing import Dict, List, Any, Optional

from src import config

logger = logging.getLogger(__name__)

FPS = 24
OUT_W, OUT_H = 1280, 720
TRANSITION_DURATION = 0.5

# camera 字段 → Ken Burns 效果
CAMERA_EFFECTS = {
    "特写": "zoom_in",
    "近景": "zoom_in",
    "中景": "zoom_in",
    "全景": "pan_right",
    "远景": "zoom_out",
}

# Ken Burns zoompan 表达式
ZOOM_EFFECTS = {
    "zoom_in": "zoompan=z='min(zoom+0.001,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "zoom_out": "zoompan=z='if(eq(on,1),1.5,max(zoom-0.001,1))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "pan_left": "zoompan=z='1.2':x='iw*(1-1/zoom)*(on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
    "pan_right": "zoompan=z='1.2':x='iw*(1-1/zoom)*(1-on/{frames})':y='ih/2-(ih/zoom/2)':d={frames}:s={w}x{h}:fps={fps}",
}

# transition 字段 → xfade 效果
XFADE_TRANSITIONS = {
    "fade": "fade",
    "dissolve": "fadeblack",
    "wipe": "wipeleft",
    "zoom": "zoom_in",
    "cut": None,
}


def _resolve_path(path: str) -> str:
    if not path:
        return ""
    if os.path.isabs(path):
        return path
    return os.path.join(str(config.ROOT_DIR_WIN), path)


def _srt_time(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


class ComicComposer:

    def compose(
        self,
        panels: List[Dict[str, Any]],
        bgm_config: Dict = None,
        project_id: int = 0,
        characters: List[Dict] = None,
    ) -> Dict[str, Any]:
        if not panels:
            return {"success": False, "error": "没有可用的分镜"}

        renderable = [p for p in panels if p.get("generated_image_path") or p.get("generated_video_path")]
        if not renderable:
            return {"success": False, "error": "没有已生成图片的分镜，请先生成分镜画面"}

        output_dir = os.path.join(config.ROOT_DIR_WIN, "static", "projects", str(project_id))
        os.makedirs(output_dir, exist_ok=True)

        from src.application.services import ffmpeg_adapter as ffmpeg

        try:
            # 1. 每个面板 → 视频片段
            video_clips = []
            for i, panel in enumerate(renderable):
                clip = self._panel_to_video(panel, output_dir, i)
                if clip:
                    video_clips.append({"path": clip, "panel": panel})

            if not video_clips:
                return {"success": False, "error": "视频片段生成失败"}

            # 2. 拼接（带转场或直连）
            if len(video_clips) == 1:
                concat_path = video_clips[0]["path"]
            else:
                has_transitions = any(
                    XFADE_TRANSITIONS.get(vc["panel"].get("transition", "cut"))
                    for vc in video_clips
                )
                if has_transitions:
                    concat_path = self._apply_transitions(video_clips, output_dir, ffmpeg)
                else:
                    concat_path = self._concat_videos([vc["path"] for vc in video_clips], output_dir, ffmpeg)

            # 3. 混合配音
            audio_path = concat_path
            dialogue_paths = self._collect_dialogue_paths(renderable)
            if dialogue_paths:
                audio_path = self._mix_dialogue_audio(concat_path, renderable, output_dir, ffmpeg)

            # 4. 混合 BGM
            final_path = audio_path
            if bgm_config and bgm_config.get("path"):
                final_path = self._mix_bgm(audio_path, bgm_config, output_dir, ffmpeg)

            # 5. 叠加字幕
            subtitle_path = final_path
            srt_content = self._generate_srt(renderable, characters)
            if srt_content:
                subtitle_path = self._burn_subtitles(final_path, srt_content, output_dir, ffmpeg)

            web_path = f"static/projects/{project_id}/{os.path.basename(subtitle_path)}"
            duration = 0
            try:
                info = ffmpeg.get_video_info(subtitle_path)
                duration = info.get("duration", 0)
            except Exception:
                pass

            return {
                "success": True,
                "output_path": web_path,
                "web_path": web_path,
                "duration": float(duration),
            }
        except Exception as e:
            logger.error(f"漫剧合成失败: {e}", exc_info=True)
            return {"success": False, "error": f"视频合成失败: {e}"}

    # ==================== 面板 → 视频片段 ====================

    def _panel_to_video(self, panel: Dict, output_dir: str, index: int) -> Optional[str]:
        from src.application.services import ffmpeg_adapter as ffmpeg

        # 优先使用已生成的视频
        video_path = panel.get("generated_video_path")
        if video_path:
            src = _resolve_path(video_path)
            if os.path.exists(src):
                dst = os.path.join(output_dir, f"clip_{index}_{uuid.uuid4().hex[:6]}.mp4")
                # 确保标准化格式
                try:
                    ffmpeg.run_ffmpeg_cmd([
                        '-y', '-i', src,
                        '-vf', f'scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p',
                        '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                        '-r', str(FPS), '-an', dst,
                    ])
                    return dst
                except Exception as e:
                    logger.warning(f"视频片段标准化失败: {e}, 尝试直接复制")

        # 图片 → Ken Burns 视频
        image_path = panel.get("generated_image_path")
        if not image_path:
            return None

        src = _resolve_path(image_path)
        if not os.path.exists(src):
            return None

        duration = panel.get("duration", 3.0)
        camera = panel.get("camera", "")
        effect_name = CAMERA_EFFECTS.get(camera, "zoom_in")
        effect_tpl = ZOOM_EFFECTS.get(effect_name, ZOOM_EFFECTS["zoom_in"])

        frames = int(duration * FPS)
        zoompan = effect_tpl.format(frames=frames, w=OUT_W, h=OUT_H, fps=FPS)

        dst = os.path.join(output_dir, f"clip_{index}_{uuid.uuid4().hex[:6]}.mp4")
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-loop', '1', '-i', src,
                '-vf', zoompan,
                '-c:v', 'libx264', '-tune', 'stillimage',
                '-pix_fmt', 'yuv420p', '-t', str(duration), '-an', dst,
            ])
            return dst
        except Exception as e:
            logger.warning(f"Ken Burns 生成失败 ({effect_name}): {e}, 回退静态")
            return self._static_image_to_video(src, duration, dst, ffmpeg)

    def _static_image_to_video(self, image_path: str, duration: float, output: str, ffmpeg) -> Optional[str]:
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-loop', '1', '-i', image_path,
                '-vf', f'scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p',
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-r', str(FPS), '-pix_fmt', 'yuv420p', '-t', str(duration), '-an', output,
            ])
            return output
        except Exception as e:
            logger.error(f"静态图片转视频失败: {e}")
            return None

    # ==================== 转场拼接 ====================

    def _apply_transitions(self, video_clips: List[Dict], output_dir: str, ffmpeg) -> str:
        paths = [vc["path"] for vc in video_clips]
        transitions = [vc["panel"].get("transition", "cut") for vc in video_clips]

        # 如果只有 cut 转场，走 concat demuxer
        if all(XFADE_TRANSITIONS.get(t) is None for t in transitions):
            return self._concat_videos(paths, output_dir, ffmpeg)

        # 逐对应用 xfade
        current = paths[0]
        cumulative_duration = 0.0

        # 获取第一段时长
        try:
            info = ffmpeg.get_video_info(current)
            cumulative_duration = float(info.get("duration", 3.0))
        except Exception:
            cumulative_duration = 3.0

        for i in range(1, len(paths)):
            transition_type = transitions[i] if i < len(transitions) else "cut"
            xfade_name = XFADE_TRANSITIONS.get(transition_type)

            if xfade_name is None:
                # cut: 直接 concat
                current = self._concat_two(current, paths[i], output_dir, ffmpeg)
                try:
                    info = ffmpeg.get_video_info(current)
                    cumulative_duration = float(info.get("duration", 3.0))
                except Exception:
                    pass
            else:
                offset = max(0, cumulative_duration - TRANSITION_DURATION)
                out = os.path.join(output_dir, f"xfade_{i}_{uuid.uuid4().hex[:6]}.mp4")
                try:
                    ffmpeg.run_ffmpeg_cmd([
                        '-y', '-i', current, '-i', paths[i],
                        '-filter_complex', f'[0:v][1:v]xfade=transition={xfade_name}:duration={TRANSITION_DURATION}:offset={offset}[v]',
                        '-map', '[v]', '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                        '-r', str(FPS), '-pix_fmt', 'yuv420p', '-an', out,
                    ])
                    current = out
                    cumulative_duration = offset + TRANSITION_DURATION
                    # 加上第二段的时长
                    try:
                        info_b = ffmpeg.get_video_info(paths[i])
                        cumulative_duration += float(info_b.get("duration", 3.0)) - TRANSITION_DURATION
                    except Exception:
                        cumulative_duration += 3.0
                except Exception as e:
                    logger.warning(f"xfade 转场失败 ({xfade_name}): {e}, 回退 concat")
                    current = self._concat_two(current, paths[i], output_dir, ffmpeg)
                    try:
                        info = ffmpeg.get_video_info(current)
                        cumulative_duration = float(info.get("duration", 3.0))
                    except Exception:
                        pass

        return current

    def _concat_videos(self, paths: List[str], output_dir: str, ffmpeg) -> str:
        concat_file = os.path.join(output_dir, f"concat_{uuid.uuid4().hex[:8]}.txt")
        with open(concat_file, 'w', encoding='utf-8') as f:
            for p in paths:
                f.write(f"file '{p}'\n")
        out = os.path.join(output_dir, f"merged_{uuid.uuid4().hex[:8]}.mp4")
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c', 'copy', out,
            ])
            return out
        except Exception:
            # stream copy 失败，重编码
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-r', str(FPS), '-pix_fmt', 'yuv420p', out,
            ])
            return out
        finally:
            try:
                os.remove(concat_file)
            except OSError:
                pass

    def _concat_two(self, a: str, b: str, output_dir: str, ffmpeg) -> str:
        concat_file = os.path.join(output_dir, f"concat2_{uuid.uuid4().hex[:6]}.txt")
        with open(concat_file, 'w', encoding='utf-8') as f:
            f.write(f"file '{a}'\nfile '{b}'\n")
        out = os.path.join(output_dir, f"cat_{uuid.uuid4().hex[:6]}.mp4")
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c', 'copy', out,
            ])
            return out
        except Exception:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-r', str(FPS), '-pix_fmt', 'yuv420p', out,
            ])
            return out
        finally:
            try:
                os.remove(concat_file)
            except OSError:
                pass

    # ==================== 配音混合 ====================

    def _collect_dialogue_paths(self, panels: List[Dict]) -> List[str]:
        paths = []
        for panel in panels:
            for p in (panel.get("generated_audio_paths") or []):
                resolved = _resolve_path(p)
                if os.path.exists(resolved):
                    paths.append(resolved)
        return paths

    def _mix_dialogue_audio(self, video_path: str, panels: List[Dict], output_dir: str, ffmpeg) -> str:
        # 收集所有配音片段及其时间偏移
        audio_entries = []
        cumulative_time = 0.0
        for panel in panels:
            duration = panel.get("duration", 3.0)
            audio_paths = panel.get("generated_audio_paths") or []
            if audio_paths:
                # 将该面板的配音放在面板时间段的中间
                for ap in audio_paths:
                    resolved = _resolve_path(ap)
                    if os.path.exists(resolved):
                        audio_entries.append({"path": resolved, "offset": cumulative_time})
            cumulative_time += duration

        if not audio_entries:
            return video_path

        out = os.path.join(output_dir, f"with_dialogue_{uuid.uuid4().hex[:6]}.mp4")

        # 构建 filter_complex: 先给视频加静音轨，然后逐个叠加配音
        inputs = ['-y', '-i', video_path]
        filter_parts = ["[0:a]anull[dialbase]"]
        prev_label = "dialbase"

        for i, entry in enumerate(audio_entries):
            inputs += ['-i', entry["path"]]
            inputs_idx = i + 1
            delay_ms = int(entry["offset"] * 1000)
            next_label = f"d{i}"
            filter_parts.append(f"[{inputs_idx}:a]adelay={delay_ms}|{delay_ms}[d{i}in]")
            filter_parts.append(f"[{prev_label}][d{i}in]amix=inputs=2:duration=first:dropout_transition=2[{next_label}]")
            prev_label = next_label

        filter_complex = ";".join(filter_parts)

        try:
            ffmpeg.run_ffmpeg_cmd(inputs + [
                '-filter_complex', filter_complex,
                '-map', '0:v', '-map', f'[{prev_label}]',
                '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                '-shortest', out,
            ])
            return out
        except Exception as e:
            logger.warning(f"配音混合失败: {e}")
            return video_path

    # ==================== BGM 混合 ====================

    def _mix_bgm(self, video_path: str, bgm_config: Dict, output_dir: str, ffmpeg) -> str:
        bgm_path = _resolve_path(bgm_config.get("path", ""))
        volume = bgm_config.get("volume", 0.3)

        if not os.path.exists(bgm_path):
            logger.warning(f"BGM 文件不存在: {bgm_path}")
            return video_path

        output = os.path.join(output_dir, f"with_bgm_{uuid.uuid4().hex[:6]}.mp4")
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video_path, '-i', bgm_path,
                '-filter_complex', f'[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first[a]',
                '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '192k',
                '-shortest', output,
            ])
            return output
        except Exception as e:
            logger.warning(f"BGM 混合失败: {e}")
            return video_path

    # ==================== 字幕生成与叠加 ====================

    def _generate_srt(self, panels: List[Dict], characters: List[Dict] = None) -> str:
        char_map = {}
        if characters:
            for c in characters:
                name = c.get("name", "")
                if name:
                    char_map[name] = name

        entries = []
        cumulative_time = 0.0
        idx = 1

        for panel in panels:
            duration = panel.get("duration", 3.0)
            dialogues = panel.get("dialogues") or []
            narration = panel.get("narration", "")

            if dialogues:
                # 对白平均分配到面板时长
                per_dlg = duration / max(len(dialogues), 1)
                for j, dlg in enumerate(dialogues):
                    text = dlg.get("text", "")
                    if not text:
                        continue
                    char_name = dlg.get("character_id") or dlg.get("characterId") or ""
                    if char_name and char_map.get(char_name, char_name):
                        text = f"【{char_name}】{text}"
                    start = cumulative_time + j * per_dlg
                    end = start + per_dlg
                    entries.append(f"{idx}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}\n")
                    idx += 1
            elif narration:
                entries.append(f"{idx}\n{_srt_time(cumulative_time)} --> {_srt_time(cumulative_time + duration)}\n{narration}\n")
                idx += 1

            cumulative_time += duration

        return "\n".join(entries)

    def _burn_subtitles(self, video_path: str, srt_content: str, output_dir: str, ffmpeg) -> str:
        srt_file = os.path.join(output_dir, f"subs_{uuid.uuid4().hex[:6]}.srt")
        with open(srt_file, 'w', encoding='utf-8') as f:
            f.write(srt_content)

        out = os.path.join(output_dir, f"final_{uuid.uuid4().hex[:6]}.mp4")

        # 转为 ASS 以支持样式
        ass_file = srt_file.replace('.srt', '.ass')
        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', srt_file, ass_file,
            ])
        except Exception:
            ass_file = srt_file

        # 转义 Windows 路径中的特殊字符
        sub_path = ass_file.replace('\\', '/').replace(':', '\\:')

        try:
            ffmpeg.run_ffmpeg_cmd([
                '-y', '-i', video_path,
                '-vf', f"subtitles='{sub_path}'",
                '-c:v', 'libx264', '-preset', 'fast', '-crf', '23',
                '-c:a', 'copy', out,
            ])
            return out
        except Exception as e:
            logger.warning(f"字幕叠加失败: {e}, 使用无字幕版本")
            return video_path
        finally:
            for f in [srt_file, ass_file]:
                try:
                    os.remove(f)
                except OSError:
                    pass
