# FFmpeg 功能与文件操作完整归纳

## 一、项目 FFmpeg 调用方式

所有 FFmpeg 调用都是 **本地命令行直接执行**，不经过任何 API 接口：

```python
# 统一执行入口：ffmpeg_adapter.py:911
subprocess.run(['ffmpeg', ...], capture_output=True, text=True, check=True)
```

**FFmpeg 二进制位置：** `ffmpeg/` 目录

---

## 二、已实现的 20 个 FFmpeg 函数

### 视频处理（本地命令行，零网络依赖）

| 函数 | FFmpeg 命令核心 | 参数 |
|------|----------------|------|
| `get_video_info` | `ffprobe -of json` | input_path |
| `process_video` | `ffmpeg -filter_complex setpts/atempo/scale/volume` | 剪切/调速/分辨率/音量/格式 |
| `cut_video` | `ffmpeg -ss start -an -c:v libx264` | input, start, end |
| `cut_video_silence` | `ffmpeg -an -vf scale=1280:720` | input, start, end |
| `extract_video_clips` | `ffmpeg -ss -t -c:v libx264`（循环） | input, interval |
| `concatenate_videos_with_filter` | `ffmpeg -filter_complex concat` | video_paths |
| `concatenate_videos_with_transitions` | 多步切割 + concat + 转场 | clip_infos |
| `compress_video_h265` | `ffmpeg -c:v hevc_nvenc/libx265` | input, crf, GPU |
| `batch_compress_videos` | ThreadPoolExecutor 并发调用 compress | input_dir |
| `set_video_cover` | `ffmpeg -disposition:v:1 attached_pic` | video, cover |
| `video_to_gif` | `ffmpeg -vf fps/scale -pix_fmt rgb24` | input, fps, scale |

### 帧处理

| 函数 | FFmpeg 命令核心 | 参数 |
|------|----------------|------|
| `extract_frame` | `ffmpeg -ss time -vframes 1 -q:v 2` | video, timestamp |
| `extract_frames` | extract_frame 循环 | video, start, end |

### 音频处理

| 函数 | FFmpeg 命令核心 | 参数 |
|------|----------------|------|
| `get_audio` | `ffmpeg -q:a 0 -map a` | video_path |
| `add_audio_to_video` | `ffmpeg -c:v copy -c:a aac -map 0:v -map 1:a` | video, audio |
| `mix_audios_to_video` | `ffmpeg -filter_complex amix=inputs=2` | video, tts, bgm, volume |

### 字幕处理

| 函数 | FFmpeg 命令核心 | 参数 |
|------|----------------|------|
| `add_subtitle` | 硬字幕: `ffmpeg -vf subtitles=` / 软字幕: `-c:s mov_text` | video, content, font |
| `str_to_ass` | `ffmpeg -i srt ass` | srt_file, ass_file |

### 通用执行

| 函数 | 说明 |
|------|------|
| `run_ffmpeg_cmd` | 通用 FFmpeg 命令执行器 |
| `safe_path` | 路径安全处理 |
| `validate_path` | 路径校验 |

---

## 三、FFmpeg 可以实现但项目未封装的功能

### A. 视频滤镜（全部本地命令行）

| 功能 | FFmpeg 滤镜 | 命令示例 |
|------|------------|---------|
| **亮度/对比度/饱和度** | `eq` | `-vf "eq=brightness=0.1:contrast=1.5:saturation=1.2"` |
| **模糊** | `gblur` | `-vf "gblur=sigma=5"` |
| **锐化** | `unsharp` | `-vf "unsharp=5:5:1.5"` |
| **旋转** | `rotate` | `-vf "rotate=PI/4"` |
| **水平/垂直翻转** | `hflip` / `vflip` | `-vf "hflip"` |
| **裁剪** | `crop` | `-vf "crop=640:480:100:100"` |
| **淡入淡出** | `fade` | `-vf "fade=t=in:st=0:d=2,fade=t=out:st=28:d=2"` |
| **画中画** | `overlay` | `-filter_complex "[1:v]scale=320:240[pi];[0:v][pi]overlay=10:10"` |
| **文字叠加** | `drawtext` | `-vf "drawtext=text='Title':fontsize=48:fontcolor=white:x=10:y=10"` |
| **水印** | `overlay` | `-i watermark.png -filter_complex "overlay=W-w-10:10"` |
| **视频倒放** | `reverse` | `-vf "reverse"` |
| **慢动作插帧** | `minterpolate` | `-vf "minterpolate='mi_mode=mci:mc_mode=aobmc:vsbmc=1:fps=60'"` |
| **视频防抖** | `vidstabtransform` | 两步：detect → transform |
| **场景检测** | `select='gt(scene,0.4)'` | 自动识别场景切换点 |
| **色彩调整** | `colorbalance` / `curves` | `-vf "curves=preset=lighter"` |
| **九宫格/视频墙** | `xstack` | 多视频拼接 |
| **倒计时** | `drawtext` + 时间表达式 | 自动生成倒计时 |

### B. 音频滤镜（全部本地命令行）

| 功能 | FFmpeg 滤镜 | 命令示例 |
|------|------------|---------|
| **音频标准化** | `loudnorm` | `-af "loudnorm=I=-16:TP=-1.5:LRA=11"` |
| **均衡器** | `equalizer` | `-af "equalizer=f=1000:t=q:w=1:g=2"` |
| **音频淡入淡出** | `afade` | `-af "afade=t=in:ss=0:d=3,afade=t=out:st=27:d=3"` |
| **回声/混响** | `aecho` | `-af "aecho=0.8:0.88:60:0.4"` |
| **降噪** | `afftdn` / `anlmdn` | `-af "afftdn=nf=-25"` |
| **变调** | `asetrate` + `atempo` | 组合实现音高变化 |
| **音频倒放** | `areverse` | `-af "areverse"` |
| **声道操作** | `pan` / `channelsplit` | 立体声↔单声道等 |

### C. 格式/容器操作（本地命令行，无需重编码）

| 功能 | 说明 |
|------|------|
| **流复制** | `-c copy` 不重编码，秒级完成 |
| **容器转换** | MP4 ↔ MKV ↔ AVI ↔ MOV 等 |
| **提取视频轨** | `-vn -c:a copy` |
| **提取音频轨** | `-an -c:v copy` |
| **合并音视频** | 不重编码直接封装 |
| **添加元数据** | `-metadata title="xxx"` |

---

## 四、文件操作能力

### 已实现的文件操作

| 操作 | 函数 | 位置 |
|------|------|------|
| 读取文本文件 | `read_text_file()` | file_util.py |
| 保存文本文件 | `save_text_file()` | file_util.py |
| 删除文件/目录 | `del_file()` | file_util.py |
| 重命名/移动 | `rename_file()` | file_util.py |
| 列出目录文件 | `get_folder_file_name()` | file_util.py |
| 获取文件名 | `get_file_name()` / `get_file_name_no_suffix()` | file_util.py |
| 获取扩展名 | `get_file_suffix()` | file_util.py |
| 检查文件存在 | `check_folder()` | file_util.py |
| 打开文件夹 | `open_folder()` | file_util.py |
| 清理目录 | `clean_upload_dir()` | file_util.py |
| 音频转 base64 | `audio_to_base64()` | file_util.py |
| 保存上传文件 | `save_uploaded_file()` | file_util.py |

### 可直接通过 Python 标准库实现的文件操作

| 操作 | 实现方式 |
|------|----------|
| **复制文件** | `shutil.copy2()` |
| **移动文件** | `shutil.move()` |
| **获取文件大小** | `os.path.getsize()` |
| **获取修改时间** | `os.path.getmtime()` |
| **计算目录大小** | `os.walk()` + `os.path.getsize()` 求和 |
| **批量重命名** | `os.rename()` + 正则匹配 |
| **文件格式转换** | 调用对应的 FFmpeg 命令 |
| **压缩/解压 ZIP** | `zipfile` 标准库 |
| **读取 JSON/CSV** | `json` / `csv` 标准库 |

---

## 五、总结：命令行直接可执行 vs 需要接口

### 100% 本地命令行（零网络依赖）

```
视频: 剪切/合并/压缩/转GIF/帧提取/封面/滤镜/旋转/翻转/裁剪/淡入淡出/
      画中画/水印/文字叠加/倒放/防抖/色彩调整/插帧/场景检测/九宫格

音频: 提取/添加/混合/标准化/均衡器/淡入淡出/回声/降噪/变调/倒放

字幕: 添加(硬/软)/格式转换/SRT↔ASS

文件: 复制/移动/删除/重命名/列表/搜索/大小/压缩

容器: 格式转换/流复制/元数据修改
```

### 需要调用 core-nexus-ai API

```
LLM 文本生成 · TTS 语音合成 · ASR 语音识别 · VL 视觉理解 · 音乐生成
```

### 需要调用第三方 API

```
Pexels/Pixabay 素材搜索下载 · yt-dlp 视频下载 · 翻译(Bing/Google/DeepL)
```
