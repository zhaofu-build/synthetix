# AI 剪辑交互优化分析

## 一、当前问题：为什么一次对话要调好几次 LLM？

### 当前 TAOR 循环机制

当前 ReAct Agent 采用 **TAOR（Think → Act → Observe → Repeat）** 循环：

```
用户输入
  → LLM 第1次调用（Think）: 思考要做什么，输出工具调用
    → 执行工具（Act）
    → 工具结果注入对话（Observe）
  → LLM 第2次调用: 看到工具结果，思考下一步，可能再输出工具调用
    → 执行工具
    → 注入结果
  → LLM 第3次调用: ...
  → ... 最多 10 轮
  → LLM 最终调用: 输出纯文本回复
```

**典型场景的 LLM 调用次数**：

| 场景 | LLM 调用次数 | 原因 |
|------|-------------|------|
| "把第一个视频剪切 00:00:05 到 00:00:10" | 0（fast path） | 正则匹配直接执行 |
| "分析第一个视频然后剪切精彩片段" | 3-4 次 | Think → list_videos → Observe → analyze_video → Observe → cut_video → Observe → 回复 |
| "帮我剪辑一个30秒的混剪视频" | 5-8 次 | 需要多步：列素材→分析→剪切×N→合并→加字幕→回复 |
| "深度研究" | 最多 31 次 | 3 个阶段 × 10 轮 + 1 次综合 |

### 为什么需要多次调用？

根本原因是 **LLM 每次只能看到已执行的工具结果**，无法一次性规划所有步骤：

1. **信息不完整**：LLM 不知道项目里有哪些素材，需要先 `list_videos` → 看结果 → 才能决定用哪个
2. **参数依赖**：`cut_video` 需要 `video_id`，而 `video_id` 来自 `list_videos` 的返回
3. **条件分支**：分析完视频后才能决定下一步是剪切、合并还是加特效
4. **结果验证**：执行完需要 LLM 确认结果是否正确

### 性能影响

每次 LLM 调用约 2-5 秒（含 KV Cache），一次完整操作 10-40 秒等待，用户体验较差。

---

## 二、现有短路优化（已实现但覆盖有限）

当前代码已有 3 个短路路径，但只能处理简单场景：

| 路径 | LLM 调用 | 覆盖场景 | 命中率 |
|------|---------|---------|--------|
| `_try_fast_path()` | 0 | 正则匹配的简单指令（"剪切第1个视频 00:00:05 到 00:00:10"） | 低 |
| `_try_tool_chain()` | 1 | 预设模板（"一键混剪"等） | 极低 |
| `_try_batch_route()` | 0 | 批量操作（"批量压缩"） | 极低 |

95%+ 的请求仍走完整 TAOR 循环。

---

## 三、优化方案：一次性规划 + 按序执行

### 核心思路

将当前的"边想边做"改为"先想清楚，再一口气做"：

```
用户输入
  → LLM 1次调用（Planning）:
    - 返回有序工具调用列表 [{tool, params}, {tool, params}, ...]
    - 标注哪些步骤需要等待外部信息（查询/下载）
  → 引擎按顺序执行工具
    - 纯本地操作（剪切/合并/加字幕）: 直接执行，不问 LLM
    - 信息查询（分析/转录）: 执行后把结果注入下一步参数
    - 下载/网络: 执行后等待完成
  → 如果所有步骤执行完毕: LLM 1次调用总结结果
  → 如果某步需要 LLM 判断: 只在该步调用 LLM（而非每步都调）
```

**LLM 调用从 N 次降到 1-2 次**（规划 + 可选的总结）。

### LLM 返回格式设计

```json
{
  "plan": [
    {
      "step": 1,
      "tool": "list_videos",
      "params": {"project_id": 7},
      "purpose": "获取素材列表",
      "wait_for_result": true
    },
    {
      "step": 2,
      "tool": "analyze_video_vl",
      "params": {"video_id": "$step1.videos[0].id", "duration": "$step1.videos[0].duration"},
      "purpose": "分析视频内容",
      "wait_for_result": true
    },
    {
      "step": 3,
      "tool": "cut_video",
      "params": {"video_id": "$step1.videos[0].id", "start_time": "00:00:05", "end_time": "00:00:15"},
      "purpose": "剪切片段",
      "wait_for_result": false
    },
    {
      "step": 4,
      "tool": "merge_videos",
      "params": {"video_ids": ["$step3.video_id"]},
      "purpose": "合并片段",
      "wait_for_result": false
    }
  ],
  "summary": "我将列出素材 → 分析视频 → 剪切精彩片段 → 合并成最终视频"
}
```

关键设计：
- `$stepN.field` 引用前序步骤结果
- `wait_for_result` 标记是否需要等结果才能继续
- 没有 `$stepN` 引用的步骤可以并行执行

### 引擎执行逻辑（伪代码）

```python
async def execute_plan(plan, state):
    results = {}
    pending_parallel = []

    for step in plan:
        # 解析参数中的 $stepN 引用
        resolved_params = resolve_references(step["params"], results)

        # 检查是否有未解析的引用（依赖未完成）
        if has_unresolved(resolved_params):
            # 先执行完并行的任务
            await gather_pending(pending_parallel)
            resolved_params = resolve_references(step["params"], results)

        if step["wait_for_result"] or has_references_to_future_steps(step, plan):
            # 必须等结果的步骤：串行执行
            result = await execute_tool(step["tool"], resolved_params)
            results[f"step{step['step']}"] = result
        else:
            # 无依赖的步骤：可以并行
            pending_parallel.append((step, resolved_params))

    # 执行剩余并行任务
    await gather_pending(pending_parallel)
    return results
```

### 需要信息补全时的处理

某些操作需要 LLM 看到中间结果后才能决策（如分析完视频内容后决定剪切哪些片段）：

```json
{
  "plan": [
    {"step": 1, "tool": "list_videos", "params": {...}, "wait_for_result": true},
    {"step": 2, "tool": "analyze_video_vl", "params": {...}, "wait_for_result": true},
    {"step": 3, "tool": "__LLM_DECIDE__", "purpose": "根据分析结果决定剪切方案"}
  ],
  "decision_points": [3]
}
```

引擎遇到 `__LLM_DECIDE__` 时暂停计划执行，将前序结果交给 LLM 做一次性决策，LLM 返回后续计划后继续执行。

---

## 四、工具分类与执行策略

### 按执行特性分类

| 类型 | 特点 | 工具举例 | 执行策略 |
|------|------|---------|---------|
| **本地计算** | 毫秒~秒级，结果确定 | cut_video, merge_videos, add_subtitle, change_speed, 滤镜类 | 直接执行，不等 LLM |
| **AI 推理** | 秒~十秒级，结果需解读 | analyze_video, analyze_video_vl, transcribe_video, detect_silence, scene_detect | 执行后结果可自动注入下一步 |
| **AI 生成** | 十秒~分钟级 | generate_tts, generate_music, generate_image, generate_video | 执行后结果可直接传给后续工具 |
| **网络下载** | 不确定时长 | download_video, search_online | 需等待，有进度 |
| **信息查询** | 即时返回，无副作用 | list_videos, get_video_detail, list_audios, search_material, get_video_description | 结果供后续步骤引用 |
| **LLM 决策** | 需要理解中间结果后判断 | （非工具，是计划中的决策点） | 暂停执行，调 LLM |

### 工具依赖链分析

大部分剪辑操作遵循以下典型管线：

```
查询类（无副作用）              操作类（有产出）            组装类（最终输出）
┌─────────────┐          ┌──────────────┐        ┌──────────────┐
│ list_videos │────┐     │ cut_video    │───┐    │ merge_videos │
│ analyze_vl  │    │     │ add_subtitle │   │    │ add_audio    │
│ transcribe  │    ├────→│ change_speed │   ├───→│ mix_audio    │
│ detect_*    │    │     │ 滤镜效果     │   │    │ compose      │
│ search_*    │────┘     │ image_to_vid │───┘    └──────────────┘
└─────────────┘          └──────────────┘
```

**关键洞察**：一旦查询阶段完成、参数确定，后续的所有操作步骤都不需要 LLM 参与——它们只是按顺序执行 FFmpeg 命令。

---

## 五、交互优化方案

### 方案 A：计划确认模式（推荐）

用户发送消息后，AI 先展示执行计划，用户确认后一次性执行：

```
用户: "帮我把第一个视频的精彩片段剪出来，加字幕，配上轻音乐"

AI 展示计划:
┌─────────────────────────────────────────────┐
│ 📋 执行计划（预计 5 步）                      │
│                                              │
│ 1. 列出项目素材            ⚡ 即时            │
│ 2. AI 分析视频内容         ~10s  🔍          │
│ 3. 剪切精彩片段（3段）     ~15s  ✂️          │
│ 4. 合并片段 + 加字幕       ~20s  🎬          │
│ 5. 生成轻音乐 + 混入音频   ~30s  🎵          │
│                                              │
│ [✏️ 修改计划]  [▶️ 开始执行]  [❌ 取消]       │
└─────────────────────────────────────────────┘

执行中:
┌─────────────────────────────────────────────┐
│ ▶️ 执行中 (3/5)                              │
│                                              │
│ ✅ 1. 列出项目素材        完成 (0.2s)        │
│ ✅ 2. AI 分析视频内容     完成 (8s)          │
│ 🔄 3. 剪切精彩片段       剪切第2段... 67%    │
│ ⏳ 4. 合并片段 + 加字幕                      │
│ ⏳ 5. 生成轻音乐 + 混入                      │
└─────────────────────────────────────────────┘
```

**优势**：
- LLM 只调用 1 次（规划）+ 可选 1 次（总结）
- 用户有控制感，可以看到并修改计划
- 执行过程可视化，进度清晰

**实现要点**：
- 新增 SSE 事件类型 `plan`（计划展示）和 `plan_confirmed`（用户确认）
- 前端新增计划面板组件，显示步骤列表和进度
- 后端新增 `plan_then_execute` 模式

### 方案 B：智能混合模式

根据指令复杂度自动选择执行模式：

| 指令类型 | 判定条件 | 执行模式 |
|---------|---------|---------|
| 简单直接 | 单工具 + 参数完整 | 直接执行（现有 fast path） |
| 多步固定 | 涉及 2-3 个工具，依赖链明确 | 一次性规划 + 按序执行 |
| 需要判断 | 涉及 AI 分析后决策 | 规划 → 执行到判断点 → LLM 决策 → 继续执行 |
| 复杂创意 | "帮我做个..."开放性请求 | 保留 TAOR 循环（作为降级） |

### 方案 C：管线模板 + 参数填充

对常见操作预定义管线模板：

```json
{
  "name": "精彩片段混剪",
  "steps": [
    {"tool": "analyze_video_vl", "params_from": "input"},
    {"tool": "cut_video", "params_from": "previous_result.highlights"},
    {"tool": "merge_videos", "params_from": "all_cut_results"},
    {"tool": "add_subtitle", "params_from": "user_config"}
  ],
  "required_inputs": ["video_id"],
  "user_config": {
    "subtitle_style": {"default": "default_preset"},
    "target_duration": {"default": 30}
  }
}
```

用户选择模板 → 填关键参数 → 一键执行，完全不需要 LLM。

---

## 六、推荐实施路径

### Phase 1：计划确认模式（核心改造）

**后端改动**：

1. `react_agent.py` 新增 `process_message_planned()` 方法
   - 第1次 LLM 调用：生成有序工具调用计划
   - yield `plan` 事件（包含步骤列表）
   - 等待前端确认
   - 按计划执行，每步 yield `plan_step_start` / `plan_step_result`
   - 最终 yield `plan_done`

2. 新增计划解析引擎 `plan_executor.py`
   - 解析 `$stepN` 引用
   - 按依赖关系串行/并行执行
   - 支持 `__LLM_DECIDE__` 决策点

3. LLM 系统提示词调整
   - 增加"规划模式"指令：要求 LLM 返回 JSON 计划而非单步工具调用
   - 提供工具依赖关系表，让 LLM 知道哪些工具可以并行

**前端改动**：

4. `ChatSidebar.vue` 新增计划面板
   - 展示步骤列表 + 预估时间
   - 确认/修改/取消按钮
   - 执行进度条

**预估效果**：80% 的场景从 3-5 次 LLM 调用降至 1-2 次，响应时间减少 50-70%。

### Phase 2：管线模板

5. 预定义 5-10 个常用管线模板
6. 前端快捷操作面板（"一键混剪""一键加字幕"等）
7. 模板参数配置 UI

### Phase 3：智能路由

8. 指令分类器（基于规则 + LLM 分类）
9. 自动选择最优执行路径
10. 保留 TAOR 作为降级方案

---

## 七、工具执行特性汇总（124 个工具）

### 可直接执行（无 LLM 参与）的操作类工具（73 个）

所有 `modify` 权限的工具，参数确定后可直接执行：

cut_video, merge_videos, image_to_video, add_subtitle, change_speed, split_video,
batch_cut, compress_video, convert_to_gif, extract_audio, mix_audio_to_video,
separate_vocal, extract_frames, reverse_video, stabilize_video, slow_motion,
set_cover, update_description, srt_to_ass, adjust_brightness, blur_video,
sharpen_video, rotate_video, flip_video, crop_video, fade_video,
picture_in_picture, add_watermark, add_text_overlay, color_adjust, convert_format,
normalize_audio, equalize_audio, fade_audio, add_echo, denoise_audio, pitch_shift,
reverse_audio, generate_tts, generate_music, retake_music, repaint_music,
edit_music_lyrics, extend_music, cover_music, style_transfer_music, generate_image,
edit_image, generate_video, image_to_video_ai, open_folder, write_file,
knowledge_add, browser_execute_js, resize_image, crop_image, rotate_image,
flip_image, adjust_image, blur_image, sharpen_image, convert_image,
compress_image, add_text_to_image, smart_clip, add_audio,
comic_generate_script, comic_edit_panel, comic_generate_image, comic_generate_video,
comic_generate_audio, comic_add_character, comic_remove_panel, comic_reorder_panels,
comic_select_bgm, download_video

### 查询类工具（44 个）

结果供后续步骤引用，本身无副作用：

list_videos, get_video_description, list_audios, list_directory, search_files,
get_current_time, get_system_info, detect_language, optimize_prompt, time_convert,
knowledge_search, search_online, browser_navigate, browser_screenshot,
browser_get_content, browser_get_links, analyze_video, analyze_video_vl,
analyze_transcript, transcribe_video, get_video_detail, extract_keyframes,
scene_detect, detect_silence, detect_scene_change, diarize_speakers, quality_check,
generate_metadata, search_material, suggest_music, random_video, batch_analyze,
plan_clip, review_result, subtitle_style_preset, list_local_files, read_local_file,
search_local_files, get_file_info, smart_clip (内部调用分析)

### 破坏性工具（7 个，需用户确认）

delete_material, manage_cache, comic_compose, rename_files, delete_files,
move_files, copy_files, create_directory

---

## 八、结论

当前 TAOR 循环的设计哲学是"笨引擎 + 聪明模型"，每步都让 LLM 决策，导致：
- **响应慢**：每次 LLM 调用 2-5s，多步操作 10-40s
- **Token 浪费**：每轮都重新读取完整对话历史 + 工具结果
- **用户体验差**：中间看到多次"思考中"跳动

**推荐方案 A（计划确认模式）**，核心改变：
1. LLM 一次调用返回完整执行计划（JSON 格式）
2. 引擎按计划执行，步骤间自动传递参数
3. 只有真正需要 LLM 判断时才再次调用
4. 用户可以预览、修改、确认计划

预期收益：80% 场景 LLM 调用从 3-5 次降至 1-2 次，整体响应时间减少 50-70%。
