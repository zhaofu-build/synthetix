# 漫剧生成融合开发方案

> 将漫剧（Manga/Comic Drama）生成能力融入 Synthetix 对话式剪辑 Agent，覆盖从文案生成到分镜、人物、场景、语音、BGM 的完整链路。所有 AI 调用统一走 core-nexus-ai 服务。

---

## 一、现有架构分析

### 已有 AI 能力（core-nexus-ai）

| 能力 | 端点 | 方法 | 状态 |
|------|------|------|------|
| LLM 文本生成 | `POST /llm` | `llm_generate_async()` | ✅ 可用 |
| LLM 流式生成 | `POST /llm/stream` | `llm_generate_stream_async()` | ✅ 可用 |
| TTS 语音合成 | `POST /tts` | `tts_generate_async()` | ✅ 可用（支持参考音频克隆） |
| ASR 语音识别 | `POST /asr` | `asr_transcribe_async()` | ✅ 可用 |
| VL 视觉理解 | `POST /vl` | `vl_generate_async()` | ✅ 可用 |
| 音乐生成 | `POST /text-to-music` | `text_to_music_async()` | ✅ 可用 |
| **图片生成** | `POST /text-to-image` | **未封装** | ❌ 需新增 |
| **视频生成** | `POST /text-to-video` | **未封装** | ❌ 需新增 |

### 现有 Agent 架构

```
用户输入 → ReAct Agent (TAOR 循环)
  → LLM 思考 → 调用工具 → 观察结果 → 继续思考
  → SSE 流式推送 (session/thinking/tool_start/tool_result/reply/done)
```

- **工具注册**: `@registry.register()` + Pydantic 参数模型 + Hook + 权限
- **已有工具**: 73 个（视频编辑、音频处理、AI 分析、素材管理等）
- **会话管理**: 内存 + DB 双写，DialogState 维护上下文
- **系统提示词链**: 基础提示词 → 项目记忆 → 技能 → 扩展 → MCP 工具

---

## 二、漫剧生成流程设计

### 整体流程

```
用户描述创意
  ↓
[1] 文案生成 → 故事脚本（角色、对话、旁白、分镜描述）
  ↓
[2] 分镜规划 → 逐镜拆解（场景描述、角色动作、构图、时长）
  ↓
[3] 角色设计 → 统一角色形象（参考图/风格描述 → 一致性图片生成）
  ↓
[4] 场景生成 → 每个分镜画面（图片生成 + 角色一致性保持）
  ↓
[5] 语音合成 → 角色对白 TTS + 旁白 TTS（不同 speaker_id 区分角色）
  ↓
[6] BGM 生成 → 音乐生成 + 音频混合（氛围匹配分镜情绪）
  ↓
[7] 视频合成 → FFmpeg 图片序列 → 视频（转场、字幕、配音、BGM 混合）
```

### 用户交互模式

用户通过对话完成所有操作，Agent 自动编排：

```
用户: "帮我做一个3分钟的校园恋爱漫剧，主角是一个安静的男生和一个活泼的女生"
Agent: 好的！我来为你生成校园恋爱漫剧。先规划故事脚本...

[工具调用] generate_script → 返回完整脚本
[工具调用] generate_storyboard → 返回分镜列表
[工具调用] generate_character("安静的男生", style="动漫") → 角色参考图
[工具调用] generate_character("活泼的女生", style="动漫") → 角色参考图
[工具调用] generate_panel_image(分镜1, 角色) → 分镜图片
...
[工具调用] generate_tts(对白, speaker_id) → 语音
[工具调用] generate_music("轻快校园BGM") → BGM
[工具调用] compose_comic_video(图片序列, 音频, BGM) → 最终视频

Agent: 漫剧已生成！共 12 个分镜，时长 2:48。点击预览查看。
```

---

## 三、技术方案

### 3.1 CoreNexusClient 扩展

**文件**: `src/shared/utils/core_nexus_client.py`

新增两个核心方法：

```python
# ==================== Image Generation 接口 ====================

def text_to_image(
    self,
    prompt: str,
    negative_prompt: str = "",
    width: int = 1024,
    height: int = 1024,
    model: Optional[str] = None,
    ref_image: Optional[str] = None,      # 参考图（图生图/IP-Adapter）
    ref_strength: float = 0.6,            # 参考图影响强度
    seed: Optional[int] = None,
    **generation_params
) -> Dict[str, Any]:
    """文本/参考图生成图片"""
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "width": width,
        "height": height,
    }
    if model: payload["model"] = model
    if ref_image: payload["ref_image"] = self._process_image_input(ref_image)
    if ref_strength: payload["ref_strength"] = ref_strength
    if seed is not None: payload["seed"] = seed
    if generation_params: payload["generation"] = generation_params

    response = self._request('POST', '/text-to-image', json_data=payload)
    return response.get('output', {})

async def text_to_image_async(self, prompt, **kwargs) -> Dict[str, Any]:
    """异步文本生成图片"""
    payload = {"prompt": prompt, **kwargs}
    if "ref_image" in payload and payload["ref_image"]:
        payload["ref_image"] = self._process_image_input(payload["ref_image"])
    response = await self._request_async('POST', '/text-to-image', json_data=payload)
    return response.get('output', {})

# ==================== Video Generation 接口 ====================

def text_to_video(
    self,
    prompt: str,
    duration: float = 3.0,
    fps: int = 8,
    model: Optional[str] = None,
    ref_image: Optional[str] = None,
    **generation_params
) -> Dict[str, Any]:
    """文本/图片生成视频"""
    payload = {"prompt": prompt, "duration": duration, "fps": fps}
    if model: payload["model"] = model
    if ref_image: payload["ref_image"] = self._process_image_input(ref_image)
    if generation_params: payload["generation"] = generation_params
    response = self._request('POST', '/text-to-video', json_data=payload)
    return response.get('output', {})

async def text_to_video_async(self, prompt, **kwargs) -> Dict[str, Any]:
    """异步文本生成视频"""
    payload = {"prompt": prompt, **kwargs}
    if "ref_image" in payload and payload["ref_image"]:
        payload["ref_image"] = self._process_image_input(payload["ref_image"])
    response = await self._request_async('POST', '/text-to-video', json_data=payload)
    return response.get('output', {})
```

### 3.2 漫剧数据模型

**文件**: `src/shared/models/comic_models.py`（新建）

```python
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from enum import Enum

class PanelTransition(str, Enum):
    CUT = "cut"
    FADE = "fade"
    DISSOLVE = "dissolve"
    WIPE = "wipe"
    ZOOM = "zoom"

class CharacterDef(BaseModel):
    """角色定义"""
    name: str = Field(description="角色名称")
    description: str = Field(description="外貌描述")
    personality: str = Field(default="", description="性格特点")
    style: str = Field(default="动漫", description="画风")
    reference_image: Optional[str] = Field(default=None, description="参考图路径")
    speaker_id: Optional[str] = Field(default=None, description="TTS speaker ID")
    voice_description: Optional[str] = Field(default=None, description="音色描述")

class StoryboardPanel(BaseModel):
    """分镜面板"""
    panel_id: int = Field(description="分镜序号")
    scene_description: str = Field(description="场景描述（用于图片生成 prompt）")
    characters: List[str] = Field(description="出镜角色名称列表")
    dialogue: Optional[str] = Field(default=None, description="对白文本")
    narration: Optional[str] = Field(default=None, description="旁白文本")
    emotion: str = Field(default="neutral", description="情绪: happy/sad/angry/neutral/tense/romantic")
    duration: float = Field(default=5.0, description="该分镜持续秒数")
    camera: str = Field(default="中景", description="镜头: 特写/近景/中景/全景/远景")
    transition_in: PanelTransition = Field(default=PanelTransition.CUT, description="入场转场")
    generated_image: Optional[str] = Field(default=None, description="生成的图片路径")
    generated_audio: Optional[str] = Field(default=None, description="生成的语音路径")

class ComicScript(BaseModel):
    """漫剧脚本"""
    title: str = Field(description="漫剧标题")
    genre: str = Field(default="", description="类型")
    style: str = Field(default="动漫", description="画风")
    total_duration: float = Field(default=60.0, description="总时长（秒）")
    characters: List[CharacterDef] = Field(description="角色列表")
    panels: List[StoryboardPanel] = Field(description="分镜列表")
    bgm_prompt: Optional[str] = Field(default=None, description="BGM 描述")
```

### 3.3 数据库实体

**文件**: `src/domain/entities/comic_project.py`（新建）

```python
class ComicProject(Base):
    """漫剧项目实体"""
    __tablename__ = 'comic_projects'

    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey('video_projects.id'), nullable=False)
    script_json = Column(Text, default='{}')          # ComicScript JSON
    characters_json = Column(Text, default='[]')       # 角色定义列表
    panels_json = Column(Text, default='[]')           # 分镜列表（含图片路径）
    bgm_path = Column(String(500), default=None)       # BGM 文件路径
    style = Column(String(50), default='动漫')          # 画风
    status = Column(String(20), default='draft')       # draft/scripting/storyboarding/generating/compositing/done
```

### 3.4 新增 Agent 工具

所有工具注册在 `src/agent/tool_registry.py`，遵循现有 `@registry.register()` 模式。

#### 工具清单

| # | 工具名 | 描述 | 权限 | 依赖 |
|---|--------|------|------|------|
| 1 | `comic_generate_script` | 根据创意描述生成漫剧脚本（角色+对白+分镜） | read_only | LLM |
| 2 | `comic_generate_character` | 生成角色参考图（保持一致性） | modify | Image Gen |
| 3 | `comic_generate_panel` | 生成分镜画面图片 | modify | Image Gen |
| 4 | `comic_generate_dialogue_audio` | 为对白生成 TTS 语音 | modify | TTS |
| 5 | `comic_generate_narration_audio` | 为旁白生成 TTS 语音 | modify | TTS |
| 6 | `comic_generate_bgm` | 根据情绪/风格生成 BGM | modify | Music |
| 7 | `comic_compose_video` | 合成漫剧视频（图片序列+音频+字幕+转场） | destructive | FFmpeg |
| 8 | `comic_preview_panel` | 预览单个分镜效果 | read_only | 无 |
| 9 | `comic_regenerate_panel` | 重新生成指定分镜 | modify | Image Gen |
| 10 | `comic_adjust_timing` | 调整分镜时间线 | modify | 无 |

#### 核心工具实现概要

**`comic_generate_script`** — 脚本生成（LLM 驱动）

```python
@registry.register(
    name="comic_generate_script",
    description="根据创意描述生成漫剧脚本，包含角色定义、分镜列表、对白和旁白",
    parameters={
        "creative": {"type": "string", "description": "创意描述，如'3分钟校园恋爱故事'"},
        "style": {"type": "string", "description": "画风: 动漫/写实/水墨/像素/美漫", "default": "动漫"},
        "duration": {"type": "number", "description": "目标时长（秒）", "default": 60},
        "num_panels": {"type": "integer", "description": "分镜数量", "default": 12},
    },
    permission="read_only",
)
async def tool_comic_generate_script(creative, style="动漫", duration=60, num_panels=12, **kwargs):
    from src.agent.prompts import COMIC_SCRIPT_PROMPT
    from src.shared.utils.core_nexus_client import get_client

    client = get_client()
    prompt = COMIC_SCRIPT_PROMPT.format(
        creative=creative, style=style, duration=duration, num_panels=num_panels
    )
    result = await client.llm_generate_async(messages=[{"role": "user", "content": prompt}])
    # 解析 LLM 返回的 JSON 脚本
    script = parse_script_json(result)
    # 保存到项目
    await save_comic_script(kwargs["project_id"], script)
    return {"script": script, "message": f"已生成 {len(script['panels'])} 个分镜的漫剧脚本"}
```

**`comic_generate_character`** — 角色参考图

```python
@registry.register(
    name="comic_generate_character",
    description="为角色生成一致性参考图，后续分镜会复用此参考",
    parameters={
        "character_name": {"type": "string", "description": "角色名称"},
        "description": {"type": "string", "description": "外貌描述"},
        "style": {"type": "string", "description": "画风", "default": "动漫"},
    },
    permission="modify",
)
async def tool_comic_generate_character(character_name, description, style="动漫", **kwargs):
    client = get_client()
    prompt = f"{style}风格，{description}，全身像，白色背景，高质量，细节丰富"
    result = await client.text_to_image_async(
        prompt=prompt, width=768, height=1024, negative_prompt="模糊,变形,低质量"
    )
    image_path = save_generated_image(result, kwargs["project_id"], f"char_{character_name}")
    # 更新角色定义
    await update_character_ref(kwargs["project_id"], character_name, image_path)
    return {"image_path": image_path, "message": f"角色 '{character_name}' 参考图已生成"}
```

**`comic_generate_panel`** — 分镜画面

```python
@registry.register(
    name="comic_generate_panel",
    description="根据分镜描述和角色参考图生成画面",
    parameters={
        "panel_id": {"type": "integer", "description": "分镜序号"},
        "scene_description": {"type": "string", "description": "场景描述"},
        "character_refs": {"type": "array", "description": "角色参考图路径列表"},
        "camera": {"type": "string", "description": "镜头", "default": "中景"},
        "emotion": {"type": "string", "description": "情绪", "default": "neutral"},
    },
    permission="modify",
)
async def tool_comic_generate_panel(panel_id, scene_description, character_refs=None,
                                     camera="中景", emotion="neutral", **kwargs):
    client = get_client()
    prompt = f"漫剧分镜，{camera}，{emotion}情绪，{scene_description}，高质量，电影感构图"
    ref_image = character_refs[0] if character_refs else None

    result = await client.text_to_image_async(
        prompt=prompt, width=1280, height=720,
        ref_image=ref_image, ref_strength=0.4,
        negative_prompt="模糊,文字水印,低质量,变形"
    )
    image_path = save_generated_image(result, kwargs["project_id"], f"panel_{panel_id:03d}")
    await update_panel_image(kwargs["project_id"], panel_id, image_path)
    return {"image_path": image_path, "message": f"分镜 {panel_id} 画面已生成"}
```

**`comic_compose_video`** — 视频合成

```python
@registry.register(
    name="comic_compose_video",
    description="将分镜图片序列、语音、BGM、字幕合成为漫剧视频",
    parameters={
        "panels": {"type": "array", "description": "分镜列表，含 image_path, duration, transition"},
        "audio_tracks": {"type": "array", "description": "音频轨道列表"},
        "bgm_path": {"type": "string", "description": "BGM 路径"},
        "bgm_volume": {"type": "number", "description": "BGM 音量", "default": 0.3},
        "resolution": {"type": "string", "description": "分辨率", "default": "1280x720"},
        "fps": {"type": "integer", "description": "帧率", "default": 24},
        "output_format": {"type": "string", "description": "输出格式", "default": "mp4"},
    },
    permission="destructive",
)
async def tool_comic_compose_video(panels, audio_tracks=None, bgm_path=None,
                                    bgm_volume=0.3, resolution="1280x720",
                                    fps=24, output_format="mp4", **kwargs):
    # 1. 构建图片序列 + 时长文件（concat demuxer）
    concat_file = build_concat_file(panels, kwargs["project_id"])

    # 2. FFmpeg 合成图片序列为视频
    video_path = run_ffmpeg_compose(concat_file, resolution, fps, kwargs["project_id"])

    # 3. 混合音频轨道（对白 + 旁白）
    if audio_tracks:
        video_path = run_ffmpeg_mix_audio(video_path, audio_tracks)

    # 4. 混合 BGM
    if bgm_path:
        video_path = run_ffmpeg_add_bgm(video_path, bgm_path, bgm_volume)

    # 5. 添加字幕（对白/旁白 burn-in）
    subtitle_path = generate_srt_from_panels(panels)
    if subtitle_path:
        video_path = run_ffmpeg_add_subtitle(video_path, subtitle_path)

    # 6. 注册为项目输出视频
    await register_output_video(kwargs["project_id"], video_path)
    return {"video_path": video_path, "message": "漫剧视频合成完成"}
```

### 3.5 系统提示词

**文件**: `src/agent/prompts.py` 新增

```python
COMIC_SCRIPT_PROMPT = """你是一个专业的漫剧编剧。请根据以下创意生成一个完整的漫剧脚本。

创意描述: {creative}
画风: {style}
目标时长: {duration}秒
分镜数量: {num_panels}个

请严格按照以下 JSON 格式输出（不要输出其他内容）:

{{
  "title": "漫剧标题",
  "genre": "类型（恋爱/搞笑/悬疑/热血/日常/奇幻）",
  "style": "{style}",
  "total_duration": {duration},
  "characters": [
    {{
      "name": "角色名",
      "description": "详细外貌描述（发色、发型、眼睛、服装、身高体型等，用于AI绘图）",
      "personality": "性格特点",
      "voice_description": "音色描述（如：清亮少女音、低沉磁性男声）"
    }}
  ],
  "panels": [
    {{
      "panel_id": 1,
      "scene_description": "详细场景描述（用于AI绘图，包含环境、光线、角色动作和表情）",
      "characters": ["出镜角色名"],
      "dialogue": "角色对白（格式：角色名：台词）或null",
      "narration": "旁白文本或null",
      "emotion": "happy/sad/angry/neutral/tense/romantic",
      "duration": 5.0,
      "camera": "特写/近景/中景/全景/远景"
    }}
  ],
  "bgm_prompt": "BGM风格描述，如：轻快钢琴曲，带有校园感"
}}

要求:
1. 每个分镜的 scene_description 必须足够详细，能直接用于AI图片生成
2. 角色描述要具体到能用于AI绘图（发色、发型、眼色、服装等）
3. 对白要自然口语化，旁白要有文学感
4. 分镜总时长接近目标时长 {duration}秒
5. 情绪曲线要有起伏（不能全程平静）
6. 镜头语言要丰富（不要全是中景）
"""

COMIC_SYSTEM_PROMPT = """
## 漫剧生成能力

你具备漫剧（Manga Drama）生成的完整能力。当用户想要创建漫剧时，按以下流程操作:

### 漫剧创作流程

**阶段 1: 脚本生成**
- 使用 `comic_generate_script` 根据用户创意生成完整脚本
- 确认角色数量、分镜数量、目标时长

**阶段 2: 角色设计**
- 对每个角色使用 `comic_generate_character` 生成参考图
- 展示给用户确认角色形象

**阶段 3: 分镜画面生成**
- 逐个分镜调用 `comic_generate_panel` 生成画面
- 使用角色参考图保持一致性（ref_image + ref_strength=0.4）
- 可以并行生成多个分镜以提高效率

**阶段 4: 语音合成**
- 对白: `comic_generate_dialogue_audio`（按角色分配不同 speaker_id）
- 旁白: `comic_generate_narration_audio`

**阶段 5: BGM 生成**
- `comic_generate_bgm` 根据整体风格生成背景音乐

**阶段 6: 视频合成**
- `comic_compose_video` 将所有素材合成最终视频

### 角色一致性策略
- 首次生成角色时，保存参考图（正面全身像）
- 后续分镜使用 ref_image 参数引用角色参考图
- ref_strength 设为 0.3-0.5（太高会复制姿势，太低会丢失特征）
- 多角色场景使用主要角色的参考图

### 画风映射
- 动漫 → prompt 前缀: "anime style, high quality, detailed"
- 写实 → "photorealistic, cinematic lighting, 8k"
- 水墨 → "chinese ink painting style, elegant"
- 像素 → "pixel art style, retro game aesthetic"
- 美漫 → "western comic style, bold lines, vibrant colors"
"""
```

### 3.6 FFmpeg 漫剧合成工具

**文件**: `src/application/services/comic_composer.py`（新建）

```python
"""漫剧视频合成服务
将图片序列 + 音频 + BGM + 字幕合成为最终视频
"""
import subprocess, tempfile, os, json
from pathlib import Path

def build_concat_file(panels, project_id):
    """构建 FFmpeg concat demuxer 文件"""
    concat_path = f"static/projects/{project_id}/comic_concat.txt"
    with open(concat_path, 'w') as f:
        for panel in panels:
            img = panel["generated_image"] or panel["image_path"]
            dur = panel.get("duration", 5.0)
            f.write(f"file '{img}'\n")
            f.write(f"duration {dur}\n")
        # 最后一帧需要重复
        last_img = panels[-1]["generated_image"] or panels[-1]["image_path"]
        f.write(f"file '{last_img}'\n")
    return concat_path

def run_ffmpeg_compose(concat_file, resolution, fps, project_id):
    """图片序列 → 视频（含转场）"""
    output = f"static/projects/{project_id}/comic_video.mp4"
    w, h = resolution.split('x')
    cmd = [
        'ffmpeg', '-y', '-f', 'concat', '-safe', '0', '-i', concat_file,
        '-vf', f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p',
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '23',
        '-r', str(fps), '-pix_fmt', 'yuv420p', output
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output

def run_ffmpeg_mix_audio(video_path, audio_tracks):
    """混合多个音频轨道到视频"""
    # 使用 amerge 或 amix 滤镜混合
    ...

def run_ffmpeg_add_bgm(video_path, bgm_path, volume=0.3):
    """添加 BGM"""
    output = video_path.replace('.mp4', '_bgm.mp4')
    cmd = [
        'ffmpeg', '-y', '-i', video_path, '-i', bgm_path,
        '-filter_complex', f'[1:a]volume={volume}[bgm];[0:a][bgm]amix=inputs=2:duration=first[a]',
        '-map', '0:v', '-map', '[a]', '-c:v', 'copy', '-shortest', output
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return output

def generate_srt_from_panels(panels):
    """从分镜生成 SRT 字幕文件"""
    srt_path = None
    current_time = 0.0
    lines = []
    idx = 1
    for panel in panels:
        dur = panel.get("duration", 5.0)
        start = current_time
        end = start + dur
        # 对白
        if panel.get("dialogue"):
            lines.append(f"{idx}\n{srt_time(start)} --> {srt_time(end)}\n{panel['dialogue']}\n")
            idx += 1
        # 旁白
        if panel.get("narration"):
            lines.append(f"{idx}\n{srt_time(start)} --> {srt_time(end)}\n{panel['narration']}\n")
            idx += 1
        current_time = end
    if lines:
        srt_path = tempfile.mktemp(suffix='.srt')
        with open(srt_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    return srt_path

def srt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
```

### 3.7 前端组件扩展

**新增面板**: `synthetix-vue/src/components/editor/ComicPanel.vue`

```
┌─────────────────────────────────────┐
│ 漫剧工作台                    [收起] │
├─────────────────────────────────────┤
│ 📝 脚本概览                         │
│ ┌─────────────────────────────────┐ │
│ │ 标题: 校园恋曲                   │ │
│ │ 角色: 2个 | 分镜: 12个 | 3:00   │ │
│ └─────────────────────────────────┘ │
│                                     │
│ 🎭 角色设计                         │
│ ┌──────┐ ┌──────┐                  │
│ │ 角色A │ │ 角色B │  [+添加角色]    │
│ │ [图片] │ │ [图片] │               │
│ │ 小明  │ │ 小红  │                 │
│ └──────┘ └──────┘                  │
│                                     │
│ 🎬 分镜时间轴                       │
│ ┌─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┬─┐       │
│ │1│2│3│4│5│6│7│8│9│10│11│12│       │
│ └─┴─┴─┴─┴─┴─┴─┴─┴─┴─┴──┴──┘       │
│                                     │
│ 📋 分镜列表                         │
│ ┌─────────────────────────────────┐ │
│ │ #1 [缩略图] 操场远景 5s ✓       │ │
│ │ #2 [缩略图] 小明特写 4s ✓       │ │
│ │ #3 [缩略图] 教室中景 5s ...     │ │
│ │ #4 [ ] 等待生成 6s              │ │
│ └─────────────────────────────────┘ │
│                                     │
│ [生成全部画面] [合成视频]           │
└─────────────────────────────────────┘
```

**前端关键交互**:
- 用户在 ChatSidebar 输入创意 → Agent 自动调用 `comic_generate_script`
- 脚本生成后，ComicPanel 自动展示脚本概览、角色卡、分镜列表
- 点击分镜可预览/重新生成
- 分镜状态实时更新（通过 SSE tool_result 事件）
- 全部就绪后点击"合成视频"

### 3.8 API 端点

**文件**: `src/interfaces/api/comic_api.py`（新建）

```python
router = APIRouter(prefix="/api/comic", tags=["漫剧"])

POST   /api/comic/script           # 生成脚本（LLM）
POST   /api/comic/character         # 生成角色参考图
POST   /api/comic/panel             # 生成分镜画面
POST   /api/comic/panel/batch       # 批量生成分镜画面
POST   /api/comic/audio/dialogue    # 生成对白语音
POST   /api/comic/audio/narration   # 生成旁白语音
POST   /api/comic/bgm               # 生成 BGM
POST   /api/comic/compose           # 合成最终视频
GET    /api/comic/{project_id}      # 获取漫剧项目数据
PUT    /api/comic/{project_id}/panel/{panel_id}  # 更新分镜
DELETE /api/comic/{project_id}/panel/{panel_id}  # 删除分镜
POST   /api/comic/{project_id}/regenerate/{panel_id}  # 重新生成分镜
```

---

## 四、角色一致性方案

这是漫剧生成的核心技术难点。

### 策略: IP-Adapter + 参考图

```
角色定义阶段:
  用户描述 → LLM 细化外貌 → text-to-image 生成角色参考图
  参考图保存为: static/projects/{id}/characters/{name}_ref.png

分镜生成阶段:
  分镜 prompt + 角色 ref_image → text-to-image(ref_strength=0.4)
  → 生成分镜画面（保持角色面部/服装一致性）

一致性增强:
  - ref_strength: 0.3-0.5（平衡一致性和自由度）
  - prompt 中固定角色外貌描述（发色、服装等关键词不省略）
  - 每个 prompt 包含 "consistent with reference character"
  - 多角色场景: 使用主角色 ref_image，prompt 描述次要角色
```

### 备选方案: LoRA 微调

如果 IP-Adapter 一致性不够，可以：
1. 用角色参考图训练轻量 LoRA（约 5-10 张即可）
2. 将 LoRA 权重部署到 core-nexus-ai 的 Stable Diffusion 服务
3. 分镜生成时指定 `lora_weights` 参数

---

## 五、实施计划

### Phase 1: 基础能力（1 周）

| 任务 | 文件 | 说明 |
|------|------|------|
| CoreNexusClient 扩展 | `core_nexus_client.py` | 新增 `text_to_image` / `text_to_video` 方法 |
| 漫剧数据模型 | `comic_models.py` | Pydantic 模型（CharacterDef, StoryboardPanel, ComicScript） |
| 数据库实体 + 迁移 | `comic_project.py` + Alembic | comic_projects 表 |
| 漫剧提示词 | `prompts.py` | COMIC_SCRIPT_PROMPT + COMIC_SYSTEM_PROMPT |

### Phase 2: 核心工具（1 周）

| 任务 | 文件 | 说明 |
|------|------|------|
| 脚本生成工具 | `tool_registry.py` | `comic_generate_script` |
| 角色生成工具 | `tool_registry.py` | `comic_generate_character` |
| 分镜画面工具 | `tool_registry.py` | `comic_generate_panel` |
| 语音合成工具 | `tool_registry.py` | `comic_generate_dialogue_audio` + `narration` |
| BGM 生成工具 | `tool_registry.py` | `comic_generate_bgm` |
| 系统提示词注入 | `react_agent.py` | Agent 识别漫剧意图后注入 COMIC_SYSTEM_PROMPT |

### Phase 3: 合成 + 前端（1 周）

| 任务 | 文件 | 说明 |
|------|------|------|
| FFmpeg 合成服务 | `comic_composer.py` | 图片序列→视频、音频混合、字幕烧录 |
| 视频合成工具 | `tool_registry.py` | `comic_compose_video` |
| REST API | `comic_api.py` | 漫剧 CRUD + 生成端点 |
| 前端 ComicPanel | `ComicPanel.vue` | 漫剧工作台面板 |
| 前端状态管理 | `project.js` (store) | comicData 状态 + debounce save |
| 路由注册 | `main.py` | 注册 comic_api router |

### Phase 4: 优化 + 打磨（3-5 天）

| 任务 | 说明 |
|------|------|
| 批量并行生成 | 多分镜图片并行调用（asyncio.gather） |
| 进度通知 | SSE 推送每个分镜的生成进度 |
| 重试 + 错误恢复 | 图片生成失败自动重试，支持断点续生成 |
| 角色一致性调优 | ref_strength 参数调优 |
| 预览优化 | 分镜即时预览 + 对比视图 |
| 快捷操作 | "一键生成全部" / "重新生成选中的" |

---

## 六、文件清单

| 文件 | 操作 | Phase |
|------|------|-------|
| `src/shared/utils/core_nexus_client.py` | 修改（+text_to_image, +text_to_video） | 1 |
| `src/shared/models/comic_models.py` | **新增** | 1 |
| `src/domain/entities/comic_project.py` | **新增** | 1 |
| `src/agent/prompts.py` | 修改（+COMIC 提示词） | 1 |
| `src/agent/tool_registry.py` | 修改（+10 个漫剧工具） | 2 |
| `src/application/services/comic_composer.py` | **新增** | 3 |
| `src/interfaces/api/comic_api.py` | **新增** | 3 |
| `src/main.py` | 修改（注册 router） | 3 |
| `synthetix-vue/src/components/editor/ComicPanel.vue` | **新增** | 3 |
| `synthetix-vue/src/store/modules/project.js` | 修改（+comicData） | 3 |
| `synthetix-vue/src/components/editor/UnifiedEditor.vue` | 修改（集成 ComicPanel） | 3 |

---

## 七、依赖关系

```
core-nexus-ai 服务需支持:
  ✅ POST /llm           — 脚本生成
  ✅ POST /tts            — 语音合成
  ✅ POST /text-to-music  — BGM 生成
  ❌ POST /text-to-image  — 需确认支持（Stable Diffusion / ComfyUI）
  ❌ POST /text-to-video  — 可选（也可用图片序列+FFmpeg替代）

本地依赖:
  ✅ FFmpeg              — 视频合成（已有）
  ✅ SQLite + Alembic    — 数据存储（已有）
  ✅ httpx               — HTTP 客户端（已有）
```

**关键前提**: core-nexus-ai 服务必须提供 `POST /text-to-image` 端点。如果暂不支持，可先用外部 API（如 Silicon Flow、Replicate）作为过渡方案，后续统一迁移到 core-nexus-ai。
