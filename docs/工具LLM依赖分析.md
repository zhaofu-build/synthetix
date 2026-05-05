# Synthetix 工具 LLM 依赖分析

> 分析哪些功能可以脱离 LLM 纯代码实现，以及哪些功能 LLM 是核心且不可替代的。

## 一、总结

| 分类 | 工具数量 | 说明 |
|------|---------|------|
| **纯代码，完全不依赖 LLM** | ~55 个 | FFmpeg 操作、数据库查询、文件管理、浏览器自动化等 |
| **依赖 AI 服务（非 LLM）** | ~6 个 | ASR 转录、TTS 合成、VL 视觉理解、音乐/图片生成 |
| **依赖 LLM，不可替代** | ~12 个 | 智能剪辑、意图理解、方案规划、创意生成等 |

---

## 二、纯代码工具（完全不依赖任何 AI）

### 2.1 视频编辑（FFmpeg）

以下工具全部通过 FFmpeg subprocess 实现，零 AI 调用：

| 工具 | 功能 | 实现方式 |
|------|------|---------|
| `cut_video` | 视频剪切 | FFmpeg `-ss` / `-to` |
| `merge_videos` | 视频合并（含转场） | FFmpeg `concat` + `xfade` |
| `add_subtitle` | 添加字幕 | FFmpeg `subtitles` / `-c:s copy` |
| `change_speed` | 变速 | FFmpeg `setpts` + `atempo` |
| `compress_video` | 压缩（H.265） | FFmpeg `-c:v libx265`，自动检测 GPU |
| `split_video` | 视频分割 | FFmpeg 段落提取 |
| `extract_frames` | 抽帧 | FFmpeg `select` 滤镜 |
| `extract_keyframes` | 关键帧提取 | FFmpeg 场景/固定/智能三种模式 |
| `convert_to_gif` | 视频转 GIF | FFmpeg palette + dither |
| `convert_format` | 格式转换 | FFmpeg 容器/编码转换 |
| `batch_compress` | 批量压缩 | FFmpeg 批量编码 |
| `batch_cut` | 批量剪切 | FFmpeg 批量段落提取 |

### 2.2 视频滤镜（FFmpeg）

| 工具 | 功能 | FFmpeg 滤镜 |
|------|------|-------------|
| `adjust_brightness` | 亮度调整 | `eq=brightness=` |
| `blur_video` | 模糊 | `gblur` |
| `sharpen_video` | 锐化 | `unsharp` |
| `rotate_video` | 旋转 | `transpose` |
| `flip_video` | 翻转 | `hflip` / `vflip` |
| `crop_video` | 裁剪 | `crop=w:h:x:y` |
| `fade_video` | 淡入淡出 | `fade=in/out` |
| `picture_in_picture` | 画中画 | `overlay` |
| `add_watermark` | 水印 | `overlay` + opacity |
| `add_text_overlay` | 文字叠加 | `drawtext` |
| `reverse_video` | 倒放 | `reverse` |
| `stabilize_video` | 防抖 | `vidstabdetect` + `vidstabtransform`（两遍） |
| `slow_motion` | 慢动作 | `minterpolate` + `setpts` |
| `color_adjust` | 色彩调整 | `eq` (gamma/saturation) |
| `scene_detect` | 场景检测 | FFmpeg `select='gt(scene,0.4)'` |

### 2.3 音频处理（FFmpeg）

| 工具 | 功能 | FFmpeg 滤镜 |
|------|------|-------------|
| `extract_audio` | 提取音频 | `-vn -c:a copy` |
| `mix_audio_to_video` | 混音到视频 | FFmpeg 多轨混合 |
| `separate_vocal` | 人声分离 | `dh_live_adapter`（本地模型） |
| `normalize_audio` | 音量标准化 | `loudnorm` |
| `equalize_audio` | 均衡器 | `equalizer` |
| `fade_audio` | 音频淡入淡出 | `afade` |
| `add_echo` | 回声 | `aecho` |
| `denoise_audio` | 降噪 | `afftdn` |
| `pitch_shift` | 变调 | `asetrate` + `atempo` |
| `reverse_audio` | 音频反转 | `areverse` |

### 2.4 图片处理（FFmpeg）

`resize_image`、`crop_image`、`rotate_image`、`flip_image`、`adjust_image`、`blur_image`、`sharpen_image`、`convert_image`、`compress_image`、`add_text_to_image` — 全部 FFmpeg 实现。

### 2.5 查询/信息工具

| 工具 | 功能 | 实现方式 |
|------|------|---------|
| `list_videos` | 素材列表 | 数据库查询 |
| `list_audios` | 音频列表 | 数据库查询 |
| `get_video_description` | 获取描述 | 数据库读取 + JSON |
| `get_video_detail` | 视频详情 | ffprobe 探测 |
| `analyze_video` | 视频分析（元数据） | ffprobe 编码/分辨率/时长 |
| `random_video` | 随机素材 | 数据库 `RANDOM()` |
| `search_files` | 文件搜索 | `os.walk` 遍历 |
| `list_directory` | 目录列表 | `os.listdir` |
| `get_current_time` | 当前时间 | `datetime.now()` |
| `get_system_info` | 系统信息 | OS/GPU/磁盘/CPU 查询 |
| `time_convert` | 时间转换 | 纯数学/字符串格式化 |
| `detect_language` | 语言检测 | Unicode 范围判断（中/日/英） |
| `srt_to_ass` | 字幕格式转换 | FFmpeg + 字符串替换 |
| `quality_check` | 质量检查 | ffprobe 分析 |

### 2.6 文件管理

`download_video`（yt-dlp）、`add_audio`、`update_description`、`delete_material`、`rename_files`、`delete_files`、`move_files`、`copy_files`、`open_folder`、`manage_cache` — 全部纯文件/数据库操作。

### 2.7 浏览器自动化

`browser_navigate`、`browser_screenshot`、`browser_get_content`、`browser_get_links`、`browser_execute_js` — 全部通过 Chrome DevTools Protocol，无 AI。

### 2.8 知识库

`knowledge_search`（BM25 关键词搜索）、`knowledge_add`（文件存储） — 本地算法，无 AI。

### 2.9 漫画管理（非生成部分）

`comic_edit_panel`、`comic_add_character`、`comic_remove_panel`、`comic_reorder_panels`、`comic_compose`（FFmpeg 合成）、`comic_select_bgm` — 数据库 JSON 操作 + FFmpeg。

---

## 三、依赖 AI 服务但非 LLM 的工具

这些工具调用 AI 推理服务，但**不需要大语言模型**（LLM），而是依赖专用模型（ASR/TTS/VL/生成模型）：

| 工具 | 依赖的 AI 服务 | 能否用纯代码替代？ | 替代方案 |
|------|---------------|-------------------|---------|
| `transcribe_video` | ASR（Whisper） | 否，语音识别必须用模型 | 可用本地 Whisper（`whisper.cpp`），去掉对 core-nexus 的依赖 |
| `generate_tts` | TTS（Fish Speech） | 否，语音合成必须用模型 | 可用本地 TTS 引擎（edge-tts、pyttsx3） |
| `generate_music` | 音乐生成模型 | 否 | 无轻量替代 |
| `analyze_video_vl` | VL（Qwen-VL） | 否，视觉理解必须用模型 | 可用本地 VL 模型 |
| `diarize_speakers` | ASR + 停顿启发式 | ASR 部分不可替代 | 说话人聚类已是纯代码 |
| `detect_silence` | 无 AI（FFmpeg） | 已是纯代码 | — |

**结论**：这类工具如果需要离线化，可以替换为本地模型，但无法用规则代码完全替代。

---

## 四、依赖 LLM 且不可替代的工具

以下工具的**核心功能**依赖 LLM，纯代码无法实现相同效果：

| 工具 | LLM 的作用 | 影响程度 |
|------|-----------|---------|
| `smart_clip` | 从创意描述提取关键词 + 生成剪辑方案 | **核心**，无 LLM 则无法理解自然语言创意 |
| `analyze_transcript` | 高光检测/主题分割/情感分析/摘要 | **核心**，纯规则效果极差 |
| `plan_clip` | LLM 驱动的剪辑规划 | **核心**，整个工具就是 LLM 规划 |
| `review_result` | LLM 驱动的质量审核 | **核心**，整个工具就是 LLM 审核 |
| `optimize_prompt` | LLM 优化用户提示词 | **核心**，优化本身就是 LLM 能力 |
| `suggest_music` | LLM 推荐配乐 | **核心**，需要理解视频内容和情感 |
| `search_online` | LLM + 联网搜索合成答案 | **核心**，需要 LLM 整合搜索结果 |
| `generate_metadata` | LLM 生成标题/标签/描述 | **核心**，创意内容生成 |
| `comic_generate_script` | LLM 生成漫画脚本 | **核心**，从描述到脚本 |
| `comic_generate_image` | AI 图片生成 | **核心**，必须用生成模型 |
| `comic_generate_video` | AI 视频生成 | **核心**，必须用生成模型 |
| `comic_generate_audio` | TTS 语音合成 | **核心**，必须用 TTS 模型 |

---

## 五、ReAct Agent 路由层 LLM 依赖分析

当前架构是 **"笨引擎 + 聪明模型"**：所有工具选择和参数解析都由 LLM 完成（`<tool_call name="...">` 格式）。这意味着即使是纯代码工具，用户也需要经过 LLM 才能调用。

### 可优化的点

| 环节 | 当前 | 纯代码替代方案 | 影响评估 |
|------|------|---------------|---------|
| **意图识别** | LLM 输出 `<tool_call name="...">` | 正则/关键词匹配 + 意图分类器 | 简单指令（"剪切 0:10-0:30"）可准确匹配；复杂/模糊指令会降质 |
| **参数提取** | LLM 从自然语言提取参数 | 正则提取时间、数字、文件名 | 结构化参数（时间、ID）效果好；语义参数（"加个浪漫滤镜"）效果差 |
| **结果解释** | LLM 组织回复语言 | 模板化回复 | 可接受，但体验略差 |
| **复杂推理** | 多轮 TAOR 循环 | 无法替代 | 这是 LLM 的核心价值 |

### 可落地的优化建议

#### 1. 快速通道（Fast Path）：跳过 LLM 的简单指令路由

对以下**确定性高**的模式，可以用正则直接匹配并调用工具，跳过 LLM：

```
"剪切视频 00:10 到 00:30"      → cut_video(start="00:00:10", end="00:00:30")
"把速度调到 1.5 倍"            → change_speed(speed=1.5)
"提取音频"                     → extract_audio()
"合并视频"                     → merge_videos()
"旋转 90 度"                   → rotate_video(angle=90)
"转成 GIF"                    → convert_to_gif()
"加字幕 xxx.srt"              → add_subtitle(file="xxx.srt")
"压缩视频"                     → compress_video()
```

**实现方式**：在 `react_agent.py` 的 `process_message()` 入口增加一个 `fast_route()` 方法，用正则匹配常见指令模式，命中则直接调用工具，不进入 TAOR 循环。

**收益**：
- 响应速度提升 10-50 倍（跳过 LLM 调用）
- 节省 token 成本
- 简单操作不需要等待 LLM 思考

**风险**：
- 需要维护正则规则库
- 边界 case 可能误匹配，需要 fallback 到 LLM

#### 2. 批量操作的本地编排

对"把所有视频都压缩一下"这类批量操作，可以：
- LLM 只做一次意图识别
- 具体遍历和调用全部由代码完成
- 减少重复的 LLM 调用

#### 3. 工具链预定义

对常见工作流（如"导出为社交媒体格式"），可以预定义工具链：
```
compress_video → resize → add_watermark → convert_to_mp4
```
用户触发时直接执行工具链，不需要 LLM 逐步决策。

---

## 六、按场景的 LLM 依赖矩阵

| 用户场景 | 是否需要 LLM | 原因 |
|---------|-------------|------|
| "把这个视频从 0:10 剪到 0:30" | ❌ 不需要 | 参数明确，可直接路由 |
| "加个字幕" | ❌ 不需要 | 操作明确 |
| "把亮度调高" | ⚠️ 可优化 | "高"需量化，可用默认值 |
| "加个浪漫的滤镜" | ✅ 需要 | "浪漫"是语义描述 |
| "帮我做一个旅行 Vlog" | ✅ 需要 | 创意理解 + 方案规划 |
| "分析这段视频讲了什么" | ✅ 需要 | 视觉理解（VL） |
| "把这个语音转成文字" | ⚠️ 需要 ASR | 非本地 ASR 不可替代 |
| "给视频配段解说" | ✅ 需要 | TTS + 文案生成 |
| "推荐一首适合的背景音乐" | ✅ 需要 | 需要理解视频情感 |
| "批量压缩所有素材" | ❌ 不需要 | 确定性批量操作 |

---

## 七、优先级建议

### P0（立即可做，收益大）

1. **快速通道路由**：对 10-15 种常见简单指令实现正则匹配 + 直接调用，跳过 LLM
2. **批量操作优化**：工具注册支持 `batch_*` 模式，一次意图识别 + 代码循环执行

### P1（短期可做，收益中等）

3. **工具链预定义**：对 5-8 种常见工作流定义模板，用户选模板直接执行
4. **结果模板化**：纯代码工具的结果用固定模板格式化，减少 LLM 组织回复的调用

### P2（长期优化）

5. **本地 ASR 替代**：集成 `whisper.cpp` 或 `faster-whisper`，去掉对 core-nexus ASR 的依赖
6. **本地 TTS 替代**：集成 `edge-tts`（免费）或 `pyttsx3`（离线），基础 TTS 不走网络
7. **意图分类小模型**：训练/微调一个小模型做意图分类，替代 LLM 的工具选择

---

## 八、关键文件索引

| 文件 | 说明 |
|------|------|
| `src/agent/tool_registry.py` | 所有工具注册（~6285 行） |
| `src/agent/react_agent.py` | ReAct Agent（TAOR 循环 + LLM 路由） |
| `src/application/services/ffmpeg_adapter.py` | 纯 FFmpeg 操作（零 AI） |
| `src/application/services/llm_adapter.py` | LLM 调用适配器 |
| `src/application/services/qwen_vl_adapter.py` | VL 视觉理解适配器 |
| `src/application/services/whisper_adapter.py` | ASR 语音识别适配器 |
| `src/application/services/fish_speech_adapter.py` | TTS 语音合成适配器 |
| `src/shared/utils/core_nexus_client.py` | 统一 AI 推理客户端 |
