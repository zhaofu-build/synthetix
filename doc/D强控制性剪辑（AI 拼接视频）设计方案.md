# 强控制性剪辑（AI 拼接视频）设计方案

## 一、功能概述

### 1.1 功能定义

**强控制性剪辑**是一种让用户对视频生成每一步都有精确控制权的剪辑方式。用户主动管理素材、编排顺序、配置参数，系统提供智能化辅助但最终决策权在用户手中。

### 1.2 与对话式剪辑的区别

| 对比项 | 对话式 AI 剪辑 | 强控制性剪辑 |
|--------|---------------|-------------|
| **交互方式** | 自然语言对话 | 可视化操作面板 |
| **决策主体** | AI 主导规划 | 用户主导控制 |
| **适用场景** | 快速出片、新手用户 | 精细制作、专业用户 |
| **学习曲线** | 零门槛 | 需要了解流程 |
| **控制粒度** | 粗粒度（整体效果） | 细粒度（每个参数） |

### 1.3 核心价值

```
┌─────────────────────────────────────────────────────────────┐
│                     强控制性剪辑价值金字塔                    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                      ┌─────────┐                            │
│                      │ 精准控制 │  ← 每个参数都可调整        │
│                    ┌─┴─────────┴─┐                          │
│                    │  流程可视   │  ← 每一步都清晰可见       │
│                  ┌─┴─────────────┴─┐                        │
│                  │   效率提升      │  ← AI 辅助减少重复劳动  │
│                ┌─┴─────────────────┴─┐                      │
│                │      结果可预期      │  ← 所见即所得        │
│              ┌─┴─────────────────────┴─┐                    │
│              │        素材可复用        │  ← 素材库持续积累  │
│            └─┴─────────────────────────┴─┘                  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、现有实现分析

### 2.1 当前架构

```
┌─────────────────────────────────────────────────────────────┐
│                    现有 VideoStitching 架构                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  前端 (VideoStitching.vue)                                  │
│  ├── 素材管理（素材库 + 使用素材列表）                       │
│  ├── 文案输入                                               │
│  ├── 音色选择 + 音频上传                                    │
│  └── 一键生成视频                                           │
│                                                             │
│  后端 (CreativeService)                                     │
│  ├── LLM 获取关键词 → 下载素材                              │
│  ├── LLM 分析素材描述                                       │
│  ├── LLM 生成剪辑方案                                       │
│  └── FFmpeg 合成视频                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 现有问题

| 问题 | 影响 | 严重程度 |
|------|------|---------|
| **黑盒执行** | 用户不知道 AI 怎么规划的 | 高 |
| **无法微调** | 生成结果不满意只能重新生成 | 高 |
| **素材选择不透明** | 不知道选了哪些素材、为什么选 | 中 |
| **缺少预览** | 无法预览剪辑方案 | 中 |
| **流程耦合** | 所有步骤绑定在一起，无法单独调整 | 中 |
| **缺少时间线** | 无法精确控制时间点 | 高 |
| **转场固定** | 无法自定义转场效果 | 低 |

### 2.3 改进方向

```
现状：一键生成 → 黑盒处理 → 输出结果
              ↓
目标：分步控制 → 透明流程 → 可调结果
```

---

## 三、系统架构设计

### 3.1 新架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           前端层 (Vue 3)                             │
├─────────────┬─────────────┬─────────────┬─────────────┬─────────────┤
│  素材管理   │  时间线编辑  │  方案配置   │  预览渲染   │  产物管理   │
│  Material   │  Timeline   │  Configure  │  Preview    │  Export     │
└─────────────┴─────────────┴─────────────┴─────────────┴─────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          业务流程层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ 素材服务    │  │ 规划服务    │  │ 执行服务    │  │ 导出服务   │  │
│  │ MaterialSvc │  │ PlannerSvc  │  │ExecutorSvc  │  │ ExportSvc  │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          核心能力层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ LLM 规划    │  │ VL 理解     │  │ TTS 合成    │  │ FFmpeg     │  │
│  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                          数据存储层                                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────────┐  │
│  │ SQLite      │  │ 文件存储    │  │ 项目缓存                    │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

### 3.2 核心流程

```
┌──────────────────────────────────────────────────────────────────────┐
│                        强控制性剪辑工作流                             │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  Step 1: 素材准备                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │  │
│  │  │ 上传素材  │ → │ AI分析   │ → │ 添加描述  │ → │ 入库管理  │    │  │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │  │
│  │        ↑                              ↑                         │  │
│  │        └──────── 搜索下载 ────────────┘                         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  Step 2: 方案规划                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │  │
│  │  │ 输入文案  │ → │ AI规划   │ → │ 方案预览  │ → │ 用户调整  │    │  │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │  │
│  │                                                       │         │  │
│  │  可调整项：素材选择 / 时间范围 / 转场效果 / 音频配置      │         │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  Step 3: 时间线编辑                                                  │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │                                                                 │  │
│  │  ┌─────────────────────────────────────────────────────────┐   │  │
│  │  │  Track 1 (Video): [===素材1===][==素材2==][====素材3====]│   │  │
│  │  │  Track 2 (Audio): [===配音===][==BGM==]                  │   │  │
│  │  │  Track 3 (Sub):   [===字幕===]                           │   │  │
│  │  │                                                         │   │  │
│  │  │  0:00      0:10      0:20      0:30      0:40      0:50 │   │  │
│  │  └─────────────────────────────────────────────────────────┘   │  │
│  │                                                                 │  │
│  │  操作：拖拽调整 / 精确裁剪 / 添加转场 / 音画同步               │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  Step 4: 音频配置                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │  │
│  │  │ TTS配音   │ → │ BGM选择  │ → │ 音量调节  │ → │ 音画同步  │    │  │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                  │                                   │
│                                  ▼                                   │
│  Step 5: 预览导出                                                    │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐    │  │
│  │  │ 实时预览  │ → │ 参数微调  │ → │ 渲染输出  │ → │ 下载分享  │    │  │
│  │  └──────────┘   └──────────┘   └──────────┘   └──────────┘    │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 四、核心模块设计

### 4.1 项目管理模块

**概念**: 每个剪辑任务是一个独立的项目，包含素材、方案、时间线等所有数据。

```python
@dataclass
class VideoProject:
    """视频项目"""
    id: str
    name: str
    created_at: datetime
    updated_at: datetime

    # 项目数据
    script: str                          # 文案
    target_duration: float               # 目标时长（秒）
    style: str                           # 风格偏好

    # 关联数据
    material_ids: List[int]              # 使用的素材ID
    clip_plan: Optional[ClipPlan]        # 剪辑方案
    timeline: Optional[Timeline]         # 时间线数据

    # 输出
    output_path: Optional[str]           # 输出文件路径
    status: str                          # draft / planning / editing / completed
```

**API 设计**:

```http
# 创建项目
POST /api/projects
{
    "name": "旅行Vlog",
    "script": "这是一个关于旅行的视频...",
    "target_duration": 60
}

# 获取项目
GET /api/projects/{project_id}

# 更新项目
PATCH /api/projects/{project_id}
{
    "clip_plan": {...},
    "timeline": {...}
}

# 保存项目
POST /api/projects/{project_id}/save

# 导出视频
POST /api/projects/{project_id}/export
```

### 4.2 素材管理模块（增强）

**现状**: 只有简单的列表和 AI 分析描述

**增强**:

```python
@dataclass
class Material:
    """视频素材"""
    id: int
    filename: str
    local_path: str
    web_path: str

    # 基础信息
    duration: float
    resolution: Tuple[int, int]
    fps: float
    file_size: int

    # AI 分析结果
    description: str                     # 内容描述
    tags: List[str]                      # 标签
    mood: str                            # 情感基调
    quality_score: float                 # 质量评分

    # 关键帧
    key_frames: List[KeyFrame]           # 关键帧列表

    # 分类
    category: str                        # 分类
    video_type: int                      # 0: 库 1: 使用中

    # 使用统计
    use_count: int                       # 使用次数
    last_used_at: Optional[datetime]
```

**新增 API**:

```http
# 素材智能搜索
POST /api/materials/search
{
    "query": "海边日出",
    "filters": {
        "min_duration": 5,
        "max_duration": 60,
        "mood": "宁静"
    }
}

# 素材标签管理
POST /api/materials/{id}/tags
{
    "tags": ["海边", "日出", "风景"]
}

# 批量分析
POST /api/materials/batch-analyze
{
    "material_ids": [1, 2, 3]
}
```

### 4.3 剪辑方案模块

**核心**: 生成可编辑的剪辑方案，而非直接执行

```python
@dataclass
class ClipPlan:
    """剪辑方案"""
    id: str
    project_id: str
    created_at: datetime

    # 方案内容
    clips: List[ClipItem]
    transitions: List[Transition]
    audio_config: AudioConfig

    # 元数据
    estimated_duration: float
    generated_by: str                    # "ai" / "manual"

@dataclass
class ClipItem:
    """剪辑片段"""
    id: str
    material_id: int
    material_name: str

    # 时间范围
    source_start: float                  # 源素材开始时间
    source_end: float                    # 源素材结束时间
    timeline_start: float                # 时间线开始时间
    timeline_end: float                  # 时间线结束时间

    # 效果
    speed: float = 1.0                   # 播放速度
    volume: float = 1.0                  # 音量

    # 描述
    purpose: str                         # 用途说明

@dataclass
class Transition:
    """转场效果"""
    type: str                            # cut / dissolve / wipe / zoom
    duration: float                      # 时长（秒）
    position: int                        # 位置（第几个片段后）

@dataclass
class AudioConfig:
    """音频配置"""
    # 配音
    voice_enabled: bool
    voice_text: str
    voice_speaker_id: Optional[int]
    voice_volume: float

    # BGM
    bgm_enabled: bool
    bgm_path: Optional[str]
    bgm_volume: float
    bgm_fade_in: float
    bgm_fade_out: float
```

**方案生成 API**:

```http
POST /api/plan/generate
{
    "project_id": "xxx",
    "script": "这是一个关于旅行的视频...",
    "material_ids": [1, 2, 3, 4, 5],
    "target_duration": 60,
    "style": "dynamic"
}

Response:
{
    "success": true,
    "data": {
        "plan_id": "plan_xxx",
        "clips": [
            {
                "id": "clip_1",
                "material_id": 1,
                "material_name": "海边日出.mp4",
                "source_start": 0,
                "source_end": 10,
                "timeline_start": 0,
                "timeline_end": 10,
                "purpose": "开场展示"
            }
        ],
        "transitions": [
            {"type": "dissolve", "duration": 0.5, "position": 1}
        ],
        "audio_config": {...},
        "estimated_duration": 60
    }
}
```

### 4.4 时间线模块

**核心**: 可视化时间线编辑

```python
@dataclass
class Timeline:
    """时间线"""
    project_id: str
    duration: float                      # 总时长

    # 轨道
    video_track: VideoTrack
    audio_tracks: List[AudioTrack]
    subtitle_track: Optional[SubtitleTrack]

@dataclass
class VideoTrack:
    """视频轨道"""
    clips: List[TimelineClip]

    def add_clip(self, clip: TimelineClip, position: int):
        pass

    def remove_clip(self, clip_id: str):
        pass

    def move_clip(self, clip_id: str, new_position: float):
        pass

    def split_clip(self, clip_id: str, split_time: float):
        pass

@dataclass
class TimelineClip:
    """时间线片段"""
    id: str
    material_id: int
    start: float                         # 开始时间
    end: float                           # 结束时间
    trim_start: float                    # 裁剪起点
    trim_end: float                      # 裁剪终点
    speed: float = 1.0
    volume: float = 1.0
```

**时间线 API**:

```http
# 获取时间线
GET /api/projects/{project_id}/timeline

# 添加片段
POST /api/timeline/clips
{
    "project_id": "xxx",
    "material_id": 1,
    "position": 10.5,
    "trim_start": 0,
    "trim_end": 5
}

# 移动片段
PATCH /api/timeline/clips/{clip_id}
{
    "start": 15.0
}

# 裁剪片段
PATCH /api/timeline/clips/{clip_id}/trim
{
    "trim_start": 2.0,
    "trim_end": 8.0
}

# 分割片段
POST /api/timeline/clips/{clip_id}/split
{
    "split_time": 5.0
}

# 添加转场
POST /api/timeline/transitions
{
    "clip_id": "clip_1",
    "type": "dissolve",
    "duration": 0.5
}
```

### 4.5 音频配置模块

```python
class AudioService:
    """音频服务"""

    async def generate_tts(
        self,
        text: str,
        speaker_id: int,
        output_path: str
    ) -> str:
        """生成 TTS 配音"""
        pass

    async def analyze_audio_duration(self, audio_path: str) -> float:
        """分析音频时长"""
        pass

    async def adjust_to_video(
        self,
        audio_path: str,
        video_duration: float,
        mode: str  # "stretch" / "trim" / "loop"
    ) -> str:
        """调整音频以匹配视频时长"""
        pass
```

### 4.6 渲染导出模块

```python
class RenderService:
    """渲染服务"""

    async def preview(
        self,
        timeline: Timeline,
        start: float = 0,
        end: float = None
    ) -> str:
        """生成预览视频（低分辨率，快速）"""
        pass

    async def render(
        self,
        timeline: Timeline,
        output_config: OutputConfig
    ) -> str:
        """渲染最终视频"""
        pass

    async def get_render_progress(self, task_id: str) -> dict:
        """获取渲染进度"""
        pass
```

---

## 五、前端界面设计

### 5.1 整体布局

```
┌─────────────────────────────────────────────────────────────────────┐
│                           顶部工具栏                                 │
│  [新建] [打开] [保存] [撤销] [重做]        [预览] [导出]            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                                                              │   │
│  │                      视频预览区                              │   │
│  │                                                              │   │
│  │                    [播放器 16:9]                             │   │
│  │                                                              │   │
│  │  [⏮] [⏯] [⏭]    00:15 / 01:00    [🔊] [全屏]               │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  时间线                                                      │   │
│  │                                                              │   │
│  │  Video:  [====素材1====][==素材2==][====素材3====]          │   │
│  │  Audio:  [======TTS配音======]   [========BGM========]      │   │
│  │  Sub:    [==字幕==]  [==字幕==]  [==字幕==]                  │   │
│  │                                                              │   │
│  │  |----|----|----|----|----|----|----|----|----|----|----|   │   │
│  │  0   10   20   30   40   50   60   70   80   90  100  110   │   │
│  │       ▲                                                     │   │
│  │    播放头                                                    │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
├──────────────────────┬──────────────────────────────────────────────┤
│                      │                                              │
│   素材库面板          │            属性面板                          │
│                      │                                              │
│  [上传] [搜索]       │   当前选中：素材1.mp4                        │
│                      │   ┌──────────────────────────────────────┐  │
│  🔍 搜索素材...      │   │ 源素材：00:00 - 00:15                 │  │
│                      │   │ 时间线：00:00 - 00:10                 │  │
│  ┌────────────────┐  │   │ 速度：1.0x                            │  │
│  │ 📹 海边日出    │  │   │ 音量：100%                            │  │
│  │    00:15       │  │   └──────────────────────────────────────┘  │
│  ├────────────────┤  │                                              │
│  │ 📹 城市街景    │  │   转场效果：                                 │
│  │    00:20       │  │   [素材1 → 素材2] 溶解 0.5s                 │
│  ├────────────────┤  │                                              │
│  │ 📹 跳伞        │  │   [添加转场]                                 │
│  │    00:30       │  │                                              │
│  └────────────────┘  │                                              │
│                      │                                              │
└──────────────────────┴──────────────────────────────────────────────┘
```

### 5.2 工作流程面板

```
┌─────────────────────────────────────────────────────────────────────┐
│                         工作流程引导                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   ① 准备素材 ─── ② 配置方案 ─── ③ 编辑时间线 ─── ④ 导出视频       │
│      ✓               ✓              ○               ○              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  当前步骤：编辑时间线                                                │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  AI 已为您规划以下方案，您可以：                               │ │
│  │                                                                │ │
│  │  • 拖拽调整片段顺序                                           │ │
│  │  • 双击片段调整时间范围                                        │ │
│  │  • 点击片段间添加转场                                          │ │
│  │  • 添加/替换 BGM                                               │ │
│  │                                                                │ │
│  │  [重新规划] [一键优化] [开始渲染]                              │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 5.3 方案确认弹窗

```
┌─────────────────────────────────────────────────────────────────────┐
│                      AI 剪辑方案                           [×]       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  根据您的文案，AI 规划了以下剪辑方案：                               │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  片段 1：海边日出.mp4                                         │ │
│  │  时间：00:00 - 00:10                                          │ │
│  │  用途：开场，展示宁静的海边日出                                │ │
│  │                                          [替换] [调整时间]     │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │  片段 2：城市街景.mp4                                         │ │
│  │  时间：00:00 - 00:15                                          │ │
│  │  用途：过渡，展示城市繁华                                      │ │
│  │                                          [替换] [调整时间]     │ │
│  ├───────────────────────────────────────────────────────────────┤ │
│  │  片段 3：跳伞.mp4                                             │ │
│  │  时间：00:05 - 00:20                                          │ │
│  │  用途：高潮，展示刺激的跳伞                                    │ │
│  │                                          [替换] [调整时间]     │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│  预计时长：60 秒                                                     │
│  转场效果：溶解 (0.5s) × 2                                          │
│  背景音乐：欢快的电子乐                                              │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐ │
│  │  配音配置                                                      │ │
│  │  ☑ 启用 TTS 配音                                              │ │
│  │  音色：[小美 - 温柔女声 ▼]                                     │ │
│  │  音量：[━━━━━━━━●━━━━━━━] 80%                                  │ │
│  └───────────────────────────────────────────────────────────────┘ │
│                                                                     │
│                              [重新规划] [确认应用到时间线]           │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 六、关键功能实现

### 6.1 方案生成与调整

```python
class ClipPlannerService:
    """剪辑方案服务"""

    async def generate_plan(
        self,
        script: str,
        materials: List[Material],
        target_duration: float,
        style: str = "balanced"
    ) -> ClipPlan:
        """
        生成剪辑方案

        Args:
            script: 文案内容
            materials: 可用素材列表
            target_duration: 目标时长
            style: 风格 (dynamic / balanced / cinematic)

        Returns:
            ClipPlan: 剪辑方案
        """
        # 1. 分析文案，提取关键主题
        themes = await self._extract_themes(script)

        # 2. 匹配素材
        matched_materials = await self._match_materials(themes, materials)

        # 3. 计算每个片段的时长分配
        clip_durations = self._calculate_durations(
            matched_materials,
            target_duration
        )

        # 4. 生成转场建议
        transitions = self._suggest_transitions(matched_materials, style)

        # 5. 构建 ClipPlan
        return ClipPlan(
            clips=self._build_clips(matched_materials, clip_durations),
            transitions=transitions,
            audio_config=self._build_audio_config(script),
            estimated_duration=target_duration
        )

    async def adjust_plan(
        self,
        plan: ClipPlan,
        adjustments: Dict
    ) -> ClipPlan:
        """
        调整方案

        Args:
            plan: 原方案
            adjustments: 调整项
                {
                    "replace_clip": {"clip_id": "x", "new_material_id": 1},
                    "adjust_duration": {"clip_id": "x", "new_duration": 10},
                    "change_transition": {"position": 1, "type": "wipe"}
                }

        Returns:
            ClipPlan: 调整后的方案
        """
        pass
```

### 6.2 时间线操作

```python
class TimelineService:
    """时间线服务"""

    def add_clip(
        self,
        timeline: Timeline,
        material_id: int,
        position: float,
        trim_start: float = 0,
        trim_end: float = None
    ) -> TimelineClip:
        """添加片段到时间线"""
        # 获取素材信息
        material = self._get_material(material_id)

        # 计算时长
        if trim_end is None:
            trim_end = material.duration
        duration = trim_end - trim_start

        # 创建片段
        clip = TimelineClip(
            id=generate_id(),
            material_id=material_id,
            start=position,
            end=position + duration,
            trim_start=trim_start,
            trim_end=trim_end
        )

        # 插入轨道
        timeline.video_track.clips.append(clip)
        timeline.video_track.clips.sort(key=lambda x: x.start)

        return clip

    def move_clip(
        self,
        timeline: Timeline,
        clip_id: str,
        new_start: float
    ) -> TimelineClip:
        """移动片段"""
        clip = self._get_clip(timeline, clip_id)
        duration = clip.end - clip.start
        clip.start = max(0, new_start)
        clip.end = clip.start + duration
        return clip

    def trim_clip(
        self,
        timeline: Timeline,
        clip_id: str,
        trim_start: float = None,
        trim_end: float = None
    ) -> TimelineClip:
        """裁剪片段"""
        clip = self._get_clip(timeline, clip_id)
        material = self._get_material(clip.material_id)

        if trim_start is not None:
            clip.trim_start = max(0, trim_start)
        if trim_end is not None:
            clip.trim_end = min(material.duration, trim_end)

        # 更新时间线时长
        clip.end = clip.start + (clip.trim_end - clip.trim_start)
        return clip

    def split_clip(
        self,
        timeline: Timeline,
        clip_id: str,
        split_time: float
    ) -> Tuple[TimelineClip, TimelineClip]:
        """分割片段"""
        clip = self._get_clip(timeline, clip_id)

        # 计算分割点
        relative_time = split_time - clip.start
        trim_split = clip.trim_start + relative_time

        # 创建两个新片段
        clip1 = TimelineClip(
            id=generate_id(),
            material_id=clip.material_id,
            start=clip.start,
            end=split_time,
            trim_start=clip.trim_start,
            trim_end=trim_split
        )

        clip2 = TimelineClip(
            id=generate_id(),
            material_id=clip.material_id,
            start=split_time,
            end=clip.end,
            trim_start=trim_split,
            trim_end=clip.trim_end
        )

        # 替换原片段
        self._replace_clip_with(timeline, clip_id, [clip1, clip2])

        return clip1, clip2
```

### 6.3 渲染执行

```python
class RenderService:
    """渲染服务"""

    async def render_timeline(
        self,
        timeline: Timeline,
        output_config: OutputConfig
    ) -> str:
        """
        渲染时间线为视频

        Args:
            timeline: 时间线数据
            output_config: 输出配置

        Returns:
            str: 输出文件路径
        """
        # 1. 准备素材片段
        segments = await self._prepare_segments(timeline.video_track)

        # 2. 应用转场
        segments_with_transitions = self._apply_transitions(
            segments,
            timeline.transitions
        )

        # 3. 合并视频
        temp_video = await self._merge_videos(segments_with_transitions)

        # 4. 处理音频
        audio_track = await self._prepare_audio(timeline)

        # 5. 音视频合成
        final_video = await self._merge_audio_video(
            temp_video,
            audio_track,
            output_config
        )

        return final_video

    async def _prepare_segments(
        self,
        video_track: VideoTrack
    ) -> List[Dict]:
        """准备视频片段"""
        segments = []
        for clip in video_track.clips:
            material = self._get_material(clip.material_id)

            # 裁剪
            trimmed = await self._trim_video(
                material.local_path,
                clip.trim_start,
                clip.trim_end
            )

            # 变速
            if clip.speed != 1.0:
                trimmed = await self._change_speed(trimmed, clip.speed)

            segments.append({
                "path": trimmed,
                "start": clip.start,
                "end": clip.end,
                "volume": clip.volume
            })

        return segments
```

---

## 七、API 接口汇总

### 7.1 项目管理

```http
POST   /api/projects                    # 创建项目
GET    /api/projects                    # 获取项目列表
GET    /api/projects/{id}               # 获取项目详情
PATCH  /api/projects/{id}               # 更新项目
DELETE /api/projects/{id}               # 删除项目
POST   /api/projects/{id}/save          # 保存项目
POST   /api/projects/{id}/export        # 导出视频
```

### 7.2 素材管理

```http
POST   /api/materials                   # 上传素材
GET    /api/materials                   # 获取素材列表
GET    /api/materials/{id}              # 获取素材详情
PATCH  /api/materials/{id}              # 更新素材信息
DELETE /api/materials/{id}              # 删除素材
POST   /api/materials/search            # 智能搜索素材
POST   /api/materials/{id}/analyze      # AI 分析素材
POST   /api/materials/batch-analyze     # 批量分析
```

### 7.3 方案规划

```http
POST   /api/plan/generate               # 生成剪辑方案
POST   /api/plan/adjust                 # 调整方案
POST   /api/plan/apply                  # 应用方案到时间线
```

### 7.4 时间线

```http
GET    /api/projects/{id}/timeline      # 获取时间线
POST   /api/timeline/clips              # 添加片段
PATCH  /api/timeline/clips/{id}         # 更新片段
DELETE /api/timeline/clips/{id}         # 删除片段
POST   /api/timeline/clips/{id}/split   # 分割片段
POST   /api/timeline/transitions        # 添加转场
DELETE /api/timeline/transitions/{id}   # 删除转场
```

### 7.5 音频

```http
POST   /api/audio/tts                   # 生成 TTS
POST   /api/audio/upload                # 上传音频
POST   /api/audio/bgm/search            # 搜索 BGM
```

### 7.6 渲染

```http
POST   /api/render/preview              # 生成预览
POST   /api/render/start                # 开始渲染
GET    /api/render/progress/{task_id}   # 获取进度
GET    /api/render/result/{task_id}     # 获取结果
```

---

## 八、前端组件结构

```
synthetix-vue/src/
├── views/
│   └── VideoStitching/
│       └── index.vue                   # 主页面
│
├── components/
│   └── VideoStitching/
│       ├── MaterialPanel.vue           # 素材面板
│       ├── MaterialLibrary.vue         # 素材库
│       ├── MaterialCard.vue            # 素材卡片
│       ├── PlanPanel.vue               # 方案面板
│       ├── PlanPreview.vue             # 方案预览
│       ├── TimelineEditor.vue          # 时间线编辑器
│       ├── TimelineTrack.vue           # 时间线轨道
│       ├── TimelineClip.vue            # 时间线片段
│       ├── AudioConfig.vue             # 音频配置
│       ├── PreviewPlayer.vue           # 预览播放器
│       ├── ExportPanel.vue             # 导出面板
│       └── WorkflowGuide.vue           # 工作流引导
│
├── stores/
│   └── videoProject.ts                 # 项目状态管理
│
├── api/
│   └── videoStitching.ts               # API 调用
│
└── composables/
    ├── useTimeline.ts                  # 时间线操作
    ├── useMaterial.ts                  # 素材操作
    └── useRender.ts                    # 渲染操作
```

---

## 九、实现路线图

### 第一阶段：基础框架（1周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 项目数据模型 | VideoProject, ClipPlan, Timeline | P0 |
| 项目 API | CRUD 接口 | P0 |
| 前端项目状态 | Pinia store | P0 |
| 基础布局 | 面板划分 | P0 |

### 第二阶段：素材管理增强（1周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 素材分析增强 | 关键帧 + 标签 | P0 |
| 素材搜索 | 语义搜索 | P1 |
| 素材面板 UI | 拖拽上传 | P0 |

### 第三阶段：方案规划（1周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 方案生成 API | LLM 规划 | P0 |
| 方案预览 UI | 可视化展示 | P0 |
| 方案调整 | 替换/修改 | P0 |

### 第四阶段：时间线编辑（2周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 时间线组件 | 拖拽交互 | P0 |
| 片段操作 | 添加/移动/裁剪/分割 | P0 |
| 转场效果 | 添加/预览 | P1 |
| 撤销/重做 | 操作历史 | P1 |

### 第五阶段：音频配置（1周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| TTS 配置 | 音色选择/音量 | P0 |
| BGM 选择 | 搜索/上传 | P1 |
| 音画同步 | 时长匹配 | P1 |

### 第六阶段：渲染导出（1周）

| 任务 | 说明 | 优先级 |
|------|------|--------|
| 预览生成 | 低分辨率快速预览 | P0 |
| 渲染 API | FFmpeg 执行 | P0 |
| 进度显示 | WebSocket 推送 | P1 |
| 导出下载 | 文件输出 | P0 |

---

## 十、与对话式剪辑的联动

两种剪辑方式可以互相补充：

```
┌─────────────────────────────────────────────────────────────────────┐
│                         剪辑模式切换                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   对话式剪辑                          强控制性剪辑                   │
│   ┌──────────────┐                   ┌──────────────┐              │
│   │  快速出片     │                   │  精细调整    │              │
│   │  AI 主导     │ ──── 切换 ────→   │  用户主导    │              │
│   │  一键生成     │ ←──── 切换 ────   │  逐步控制    │              │
│   └──────────────┘                   └──────────────┘              │
│                                                                     │
│   联动方式：                                                         │
│   1. 对话式生成方案 → 导出到强控制模式微调                           │
│   2. 强控制模式保存模板 → 对话式快速复用                             │
│   3. 对话中指定参数 → 自动跳转到强控制模式对应位置                   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**联动 API**:

```http
# 从对话模式导出到强控制模式
POST /api/agent/export-to-studio
{
    "session_id": "xxx",
    "plan": {...}
}

# 从强控制模式保存为技能
POST /api/projects/{id}/save-as-skill
{
    "skill_name": "我的Vlog模板",
    "description": "..."
}
```

---

## 十一、总结

### 核心改进点

| 改进点 | 现状 | 目标 |
|--------|------|------|
| **执行模式** | 一键黑盒执行 | 分步可控执行 |
| **方案展示** | 无预览 | 可视化预览 |
| **调整能力** | 只能重新生成 | 每步可微调 |
| **时间控制** | 无精确控制 | 时间线精确编辑 |
| **转场效果** | 固定效果 | 可选择配置 |
| **音频处理** | 简单合成 | 多轨配置 |

### 预期效果

1. **用户掌控感**：每一步都清楚发生了什么
2. **结果可预期**：预览与最终输出一致
3. **效率提升**：AI 辅助 + 用户微调 = 最佳效率
4. **可复用性**：方案和模板可保存复用

---

*文档版本：v1.0*
*创建日期：2026-04-05*
