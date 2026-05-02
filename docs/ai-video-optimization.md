# Synthetix AI 视频剪辑优化方案

## 一、现状分析

### 1.1 当前处理流程

当前 AI 视频分析采用**全量发送**模式：

```
用户请求 → 获取视频 → 生成代理(>1080p/30min) → 整视频 base64 编码 → VL API → 返回结果
```

关键瓶颈：

| 环节 | 问题 | 影响 |
|------|------|------|
| VL 输入 | 整个视频 base64 编码后一次性发送 | 高内存占用、网络传输慢 |
| 代理生成 | 仅对 >1080p 或 >30min 视频生成 540p 代理 | 中等视频仍全量处理 |
| 特征提取 | 每次分析独立计算，无帧级/场景级复用 | 重复计算严重 |
| 智能剪辑 | `smart_clip` 用 ASR 字幕替代 VL，但仍是逐视频转录 | 长视频耗时巨大 |
| 缓存策略 | 基于文件路径+prompt hash 的结果缓存（4h TTL） | 换 prompt 即失效，粒度太粗 |

### 1.2 现有优化机制

项目已具备的优化基础：

- **代理生成**：`ffmpeg_adapter.generate_proxy()` 将大视频压缩到 540p/15fps
- **结果缓存**：`result_cache.py` 文件级缓存，VL 4h/ffprobe 1h
- **ASR 缓存**：Whisper 转录结果缓存
- **关键帧提取**：`extract_keyframes()` 支持 fixed/scene/smart 三种模式（但未接入 VL 流程）
- **场景检测**：`detect_scene_changes()` 已实现（但结果未持久化）
- **多 Agent**：Planner→Executor→Reviewer 三阶段流水线
- **并行剪辑**：`extract_clips_parallel()` 使用线程池并行提取片段

### 1.3 核心矛盾

**已有的关键帧提取、场景检测能力与 VL 分析流程完全断裂。** `extract_keyframes()` 和 `detect_scene_changes()` 仅作为独立工具暴露给 Agent，而 `analyze_video_vl` 仍将整视频发送给 VL，未利用这些预处理能力。

---

## 二、优化方案总览

```
┌─────────────────────────────────────────────────────────────┐
│                      优化前 vs 优化后                        │
├──────────────────┬──────────────────────────────────────────┤
│ 优化前           │ 优化后                                   │
├──────────────────┼──────────────────────────────────────────┤
│ 整视频 → VL      │ 关键帧 + 结构化元数据 → LLM              │
│ 每次全量计算      │ 镜头级持久化缓存 + 增量更新               │
│ 单一模型处理      │ 轻量模型预处理 + 大模型关键决策            │
│ 粗粒度文件缓存    │ 镜头级向量缓存 + 语义检索                 │
│ 同步阻塞处理      │ 流式渐进处理 + 流水线并行                  │
└──────────────────┴──────────────────────────────────────────┘
```

---

## 三、核心优化方案

### 3.1 视频结构化预处理管线（最高优先级）

**目标**：将视频离散化为结构化语义单元，避免 VL 处理原始视频流。

**实现路径**：串联已有的 `detect_scene_changes()` + `extract_keyframes()` + ASR，构建"视频结构化索引"。

```
原始视频
    │
    ├─→ 镜头边界检测 (OpenCV/FFmpeg scene detect)  → shots[]
    │     每个 shot: {start_time, end_time, type, confidence}
    │
    ├─→ 关键帧提取 (已有的 extract_keyframes smart 模式)
    │     每个 shot 提取 1-3 帧代表帧
    │
    ├─→ ASR 字幕生成 (已有的 Whisper transcribe)
    │     对齐到镜头时间戳 → shot.subtitle_text
    │
    └─→ 结构化描述拼接
          "{镜头类型}: {关键帧视觉描述}, 台词'{字幕文本}'"
          → shot.structured_description
```

**落地步骤**：

1. **新建 `VideoIndexer` 服务**（`src/application/services/video_indexer.py`）：

```python
class VideoIndexer:
    """视频结构化索引服务"""

    async def index_video(self, video_id: int) -> VideoIndex:
        """
        将视频解构为结构化索引。
        输出: VideoIndex(shots, scenes, keyframes, subtitles)
        """
        # 1. 场景/镜头检测（复用 ffmpeg_adapter.detect_scene_changes）
        shots = await self._detect_shots(video_path)

        # 2. 关键帧提取（复用 ffmpeg_adapter.extract_keyframes smart 模式）
        keyframes = await self._extract_keyframes(video_path, shots)

        # 3. ASR 字幕（复用 whisper_adapter.transcribe）
        subtitles = await self._transcribe(video_path)

        # 4. 时间对齐：将字幕与镜头关联
        aligned = self._align_shots_with_subtitles(shots, subtitles)

        # 5. 持久化到数据库
        return await self._save_index(video_id, aligned, keyframes)

    async def _detect_shots(self, video_path: str) -> List[Shot]:
        """镜头边界检测"""
        scenes = ffmpeg.detect_scene_changes(video_path)
        return [Shot(start=s['start'], end=s['end'],
                     type=s.get('type', 'unknown'))
                for s in scenes]
```

2. **新建数据库实体 `VideoIndex`/`Shot`**（`src/domain/entities/video_index.py`）：

```python
class Shot(Base):
    __tablename__ = 'video_shots'
    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey('video_sources.id'))
    start_time = Column(Float)        # 秒
    end_time = Column(Float)
    shot_type = Column(String(50))    # closeup/medium/wide/unknown
    keyframe_paths = Column(JSON)     # ["shot_001_frame1.jpg", ...]
    subtitle_text = Column(Text)      # 该镜头内的台词
    description = Column(Text)        # AI 生成的结构化描述
    embedding_vector = Column(LargeBinary)  # CLIP 向量（可选）
    scene_group = Column(Integer)     # 场景聚类 ID
```

3. **修改 `analyze_video_vl` 工具**：

```python
# 修改前：整视频发送给 VL
async def tool_analyze_video_vl(video_id, prompt, **kwargs):
    proxy = ffmpeg.generate_proxy(video.path)
    result = qwen_vl.video_summary(proxy, prompt, video.duration)

# 修改后：基于结构化索引生成描述
async def tool_analyze_video_vl(video_id, prompt, **kwargs):
    index = await video_indexer.get_or_create_index(video_id)
    if index.is_complete:
        # 索引已完整，直接拼接结构化描述发给 LLM（非 VL）
        context = index.to_structured_context()
        return await llm_adapter.generate_response_async(
            f"基于以下视频结构化索引回答:\n{context}\n\n用户问题: {prompt}"
        )
    else:
        # 降级到 VL（首次处理或索引不完整）
        return await _fallback_vl_analysis(video, prompt)
```

**效果预估**：

| 指标 | 优化前 | 优化后 |
|------|--------|--------|
| VL API 调用 | 每次分析必调用 | 仅首次索引时调用 |
| 计算量 | 处理全部帧（数万帧） | 仅处理关键帧（1%-5%） |
| 后续查询延迟 | 5-30s（取决于视频长度） | <1s（检索结构化索引） |
| 资源消耗 | 高显存（VL 模型需要） | 极低（文本检索） |

---

### 3.2 分层缓存策略

**目标**：从文件级粗粒度缓存升级为镜头级细粒度缓存，支持跨任务复用。

**缓存层级**：

```
L1: 内存缓存（热数据，LRU，5分钟 TTL）
    └─ 最近分析的视频索引、频繁查询的镜头特征

L2: 本地文件缓存（温数据，result_cache.py 增强）
    └─ ASR 结果、场景检测结果、VL 分析结果

L3: 数据库持久化（冷数据，Shot 表）
    └─ 镜头级元数据、CLIP 向量、结构化描述

L4: 向量索引（可选，FAISS）
    └─ 镜头级 embedding，支持语义检索
```

**增强 `result_cache.py`**：

```python
class ResultCache:
    # 新增：镜头级缓存键
    @staticmethod
    def shot_cache_key(video_id: int, shot_index: int, analysis_type: str) -> str:
        return f"shot:{video_id}:{shot_index}:{analysis_type}"

    # 新增：基于内容的缓存（而非基于 prompt hash）
    # 相似 prompt 命中同一缓存（用 embedding cosine similarity > 0.95）
    def get_by_similarity(self, prefix: str, query_embedding: np.ndarray,
                          threshold: float = 0.95) -> Optional[Any]:
        ...
```

**增量更新**：当视频局部修改（剪切/合并）时，仅重新索引变动片段：

```python
async def incremental_update_index(self, video_id: int,
                                     changed_ranges: List[Tuple[float, float]]):
    """仅重新处理变更时间段内的镜头"""
    existing = await self._load_index(video_id)
    for start, end in changed_ranges:
        affected_shots = [s for s in existing.shots
                          if s.start_time < end and s.end_time > start]
        # 仅重新分析受影响的镜头
        for shot in affected_shots:
            await self._reindex_shot(video_id, shot)
```

---

### 3.3 渐进式视频分析

**目标**：用"粗→细"渐进分析替代一次性全量处理。

**流程**：

```
Level 0（毫秒级）：视频元数据
    → duration, resolution, codec, file_size

Level 1（秒级）：结构化索引
    → 镜头列表、场景边界、关键帧缩略图

Level 2（十秒级）：文本分析
    → ASR 字幕 + 基于字幕的语义分析

Level 3（分钟级）：视觉分析（按需）
    → 关键帧 VL 描述、CLIP 向量、镜头类型分类

Level 4（深度，仅用户触发）：完整 VL 分析
    → 逐镜头视觉理解、叙事链提取
```

**实现**：修改 `analyze_video_vl` 支持多级分析：

```python
async def tool_analyze_video_vl(video_id, prompt, depth="auto", **kwargs):
    """
    depth 参数：
    - "quick":   仅 L0+L1（元数据+结构索引）
    - "normal":  L0-L2（+ASR 字幕分析）
    - "deep":    L0-L3（+关键帧 VL）
    - "full":    L0-L4（完整 VL 分析）
    - "auto":    根据视频时长自动选择
    """
    if depth == "auto":
        depth = "quick" if video.duration < 60 else \
                "normal" if video.duration < 300 else \
                "deep" if video.duration < 1800 else "full"

    # 逐级加载，命中缓存则跳过
    result = {}
    result.update(await self._level_0_metadata(video))       # 始终执行
    if depth in ("normal", "deep", "full"):
        result.update(await self._level_1_structure(video))   # 有缓存则秒返回
    if depth in ("normal", "deep", "full"):
        result.update(await self._level_2_text(video))        # ASR 有缓存则秒返回
    if depth in ("deep", "full"):
        result.update(await self._level_3_visual(video))      # 关键帧 VL
    if depth == "full":
        result.update(await self._level_4_deep(video, prompt)) # 完整 VL

    return result
```

---

### 3.4 模型架构优化：减少 VL 调用

#### 3.4.1 关键帧 VL 替代全视频 VL

当前 `video_summary()` 将整视频 base64 发给 VL。优化方案：

```python
async def video_summary_optimized(self, video_id: int, prompt: str):
    """用关键帧序列替代整视频发送"""
    index = await video_indexer.get_or_create_index(video_id)

    # 策略1：短视频（<5min），关键帧 < 20 张 → 批量发送关键帧给 VL
    if len(index.keyframes) <= 20:
        keyframe_urls = [kf.to_data_url() for kf in index.keyframes]
        return await core_nexus.vl_generate(
            prompt=enhanced_prompt, images=keyframe_urls
        )

    # 策略2：中长视频（5-60min），先用结构化索引 + LLM 生成摘要
    context = index.to_structured_context()
    return await core_nexus.llm_generate_async(
        f"基于以下视频结构化索引回答:\n{context}\n\n{prompt}"
    )

    # 策略3：超长视频（>60min），仅对关键片段调用 VL
    # 先用 LLM 从索引中筛选关键片段，再对片段调用 VL
```

#### 3.4.2 交错 MRoPE（长期方向）

对于原生支持长视频的模型（如 Qwen3-VL 256K 上下文），可采用：

- 在时间/宽度/高度三维度独立分配位置编码
- 避免传统 Transformer 对长视频的 O(n²) 计算开销
- 这是模型层面的优化，依赖 core-nexus-ai 服务端支持

#### 3.4.3 分解注意力机制（长期方向）

- 将全注意力拆解为视觉内部注意力、文本自注意力、跨模态注意力
- 复杂度从 O(n²) 降至 O(n)
- 适用于超长视频（>1 小时），依赖专用模型（如 Vidi2）

---

### 3.5 多智能体协作优化

#### 3.5.1 增强 Agent 分工

当前 `multi_agent.py` 的 Planner→Executor→Reviewer 已有基础框架，但 Planner 和 Reviewer 缺乏工具调用能力。优化方向：

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ 解构 Agent  │────→│ 编剧 Agent  │────→│ 剪辑 Agent  │────→│ 审阅 Agent  │
│ (轻量模型)  │     │ (慢模型)    │     │ (快模型)    │     │ (慢模型)    │
│             │     │             │     │             │     │             │
│ · 镜头分割  │     │ · 叙事规划  │     │ · 局部剪辑  │     │ · 质量验证  │
│ · ASR 转录  │     │ · 音乐结构  │     │ · 片段检索  │     │ · 连贯性    │
│ · 关键帧    │     │ · 节奏控制  │     │ · 转场生成  │     │ · 最终确认  │
│ · 场景聚类  │     │             │     │             │     │             │
│ 输出: 索引  │     │ 输出: 计划  │     │ 输出: 视频  │     │ 输出: 评分  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
    无 VL 调用          无视频访问          仅局部片段          仅验证候选
```

**关键改进**：

1. **解构 Agent** 使用轻量模型 + 本地算法，不调用 VL
2. **编剧 Agent** 仅读取结构化索引，不访问原始视频
3. **剪辑 Agent** 仅处理编剧指定的局部片段
4. **审阅 Agent** 仅验证最终候选，而非全流程参与

#### 3.5.2 并行 Agent 执行

当前 `run_pipeline()` 是严格串行的。对于独立任务（如多段视频分别分析），可并行执行：

```python
async def run_parallel_pipeline(tasks: List[AgentTask]) -> List[AgentResult]:
    """并行执行多个独立 Agent 任务"""
    async with asyncio.TaskGroup() as tg:
        futures = [tg.create_task(run_sub_agent(task.role, task))
                   for task in tasks]
    return [f.result() for f in futures]
```

---

### 3.6 向量检索增强（可选，中优先级）

**目标**：建立镜头级特征向量库，支持语义检索。

```python
class ShotVectorStore:
    """镜头级向量检索服务"""

    def __init__(self):
        self.index = faiss.IndexFlatIP(512)  # CLIP ViT-B/32 维度
        self.shot_map = {}  # FAISS index → Shot ID 映射

    async def index_video(self, video_id: int):
        """为视频的所有关键帧生成 CLIP 向量并入库"""
        shots = await self._get_shots(video_id)
        for shot in shots:
            for keyframe_path in shot.keyframe_paths:
                vector = await self._encode_image(keyframe_path)
                idx = self.index.ntotal
                self.index.add(vector.reshape(1, -1))
                self.shot_map[idx] = shot.id

    async def search(self, query: str, top_k: int = 10) -> List[Shot]:
        """根据文本描述检索最相关的镜头"""
        query_vector = await self._encode_text(query)
        scores, indices = self.index.search(query_vector.reshape(1, -1), top_k)
        return [await self._get_shot(self.shot_map[i]) for i in indices[0]]
```

**应用场景**：
- `search_material` 工具可用向量检索替代关键词匹配
- `smart_clip` 可快速定位与创意描述匹配的镜头
- Agent 对话中"找一段人物特写"→ 直接向量检索

---

### 3.7 硬件加速优化

#### 3.7.1 GPU 加速帧提取

当前 FFmpeg 帧提取使用 CPU。可利用 NVIDIA GPU 的 NVDEC 硬件解码器：

```python
def extract_frames_gpu(self, video_path: str, output_dir: str,
                       timestamps: List[float]) -> List[str]:
    """GPU 加速帧提取"""
    # 检测 NVDEC 可用性
    encoder = self._best_encoder  # 已有检测逻辑
    if 'nvenc' in encoder:
        # 使用 hwaccel_cuda 加速解码
        cmd = [
            'ffmpeg', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda',
            '-i', video_path, '-vf', f"select='eq(n\\,0)'",
            '-vsync', 'vfr', '-q:v', '2', output_pattern
        ]
    else:
        # 降级到 CPU（已有逻辑）
        ...
```

#### 3.7.2 Decord 高性能帧采样

对于需要大量帧采样的场景（如 CLIP 向量提取），使用 Decord 替代 FFmpeg：

```python
# pip install decord
from decord import VideoReader, gpu

def sample_frames_decord(video_path: str, num_frames: int = 8) -> List[np.ndarray]:
    """使用 Decord 进行高性能帧采样"""
    vr = VideoReader(video_path, ctx=gpu(0))  # GPU 解码
    indices = np.linspace(0, len(vr) - 1, num_frames, dtype=int)
    frames = vr.get_batch(indices).asnumpy()
    return frames
```

Decord 比 FFmpeg 子进程调用快 5-10 倍，特别适合批量帧提取场景。

---

### 3.8 流式处理与用户体验优化

#### 3.8.1 VL 分析流式返回

当前 `analyze_video_vl` 同步返回完整结果。对于长视频，改为渐进式流式返回：

```python
async def analyze_video_vl_stream(self, video_id: int, prompt: str):
    """流式返回分析结果，先快后细"""
    # 立即返回 L0 元数据
    yield {"level": 0, "type": "metadata", "data": video_metadata}

    # 快速返回结构索引
    index = await video_indexer.get_or_create_index(video_id)
    yield {"level": 1, "type": "structure", "data": index.summary()}

    # ASR 完成后返回文本分析
    transcript = await whisper_adapter.transcribe(video_path)
    yield {"level": 2, "type": "transcript", "data": transcript}

    # VL 关键帧分析（最耗时，按镜头流式返回）
    for shot in index.shots:
        analysis = await self._analyze_shot(shot, prompt)
        yield {"level": 3, "type": "shot_analysis", "data": analysis}
```

#### 3.8.2 前端渐进展示

前端 `VideoAnalysis.vue` 可改为分段展示：

```
[立即] 视频信息面板（分辨率、时长、编码）
[1-2s] 镜头列表（缩略图 + 时间范围）
[5-10s] 字幕/台词面板
[10-60s] AI 分析结果逐镜头流式显示
```

#### 3.8.3 后台预处理

视频导入/上传时自动触发后台索引：

```python
# 在素材注册后自动触发
async def register_material(video_path: str, project_id: int):
    video = await save_to_db(video_path, project_id)
    # 后台异步构建索引，不阻塞用户操作
    asyncio.create_task(video_indexer.index_video(video.id))
    return video
```

---

## 四、与原文档方案的补充对比

### 4.1 原文档方案评估

| 原方案 | 评估 | 补充建议 |
|--------|------|----------|
| 镜头边界检测 + CLIP 聚类 | 方向正确，但 CLIP 聚类开销大 | 先用 FFmpeg scene detect（已有），CLIP 向量作为可选增强 |
| 交错 MRoPE（256K 上下文） | 需要专用模型支持 | 短期不可控，作为长期方向标注 |
| 分解注意力（Vidi2） | 依赖外部模型，部署成本高 | 仅在超长视频场景（>1h）考虑 |
| 解构/编剧/剪辑/审阅 Agent | 与现有 multi_agent.py 吻合 | 增强现有 Agent 而非重写 |
| FAISS 向量索引 | 适合大规模素材库 | 小型项目（<100 视频）用 SQLite 即可 |
| GPU NVDEC + Decord | 合理，前端帧提取可提速 5-10x | Decord 引入额外依赖，可渐进式集成 |

### 4.2 原文档未覆盖的优化点

1. **渐进式分析（分层加载）**：原文档仅讨论"全量预处理"，未提及按需逐级加载策略
2. **现有能力串联**：`detect_scene_changes()` + `extract_keyframes()` + ASR 已存在但未打通
3. **后台预处理**：视频导入时自动构建索引，对用户透明
4. **流式 VL 返回**：原文档关注模型架构，未涉及前端渐进式体验
5. **缓存语义化**：从 prompt hash 匹配升级到语义相似度匹配
6. **增量索引更新**：视频局部修改时仅重算变更部分

---

## 五、实施优先级与路线图

### Phase 1：低成本高收益（1-2 周）

| 任务 | 改动范围 | 预期收益 |
|------|----------|----------|
| 串联 scene_detect + extract_keyframes + ASR → 结构化索引 | 新增 `video_indexer.py` + Shot 实体 | VL 调用减少 80%+ |
| `analyze_video_vl` 优先读索引，降级到 VL | 修改 `tool_registry.py` | 后续查询延迟从 5-30s 降至 <1s |
| 素材注册后自动后台索引 | 修改素材注册流程 | 用户无感知预处理 |
| 增强缓存：镜头级粒度 | 修改 `result_cache.py` | 跨任务复用率提升 |

### Phase 2：中等投入（2-4 周）

| 任务 | 改动范围 | 预期收益 |
|------|----------|----------|
| 渐进式分析 API（depth 参数） | 修改 VL 分析流程 | 短视频秒级响应 |
| 多 Agent 并行执行 | 修改 `multi_agent.py` | 多段视频并行处理提速 |
| 关键帧 VL 替代全视频 VL | 修改 `qwen_vl_adapter.py` | VL 调用量减少 90% |
| 流式 VL 返回 + 前端渐进展示 | 前后端联动 | 用户体验显著提升 |

### Phase 3：深度优化（1-2 月，按需）

| 任务 | 改动范围 | 预期收益 |
|------|----------|----------|
| CLIP 向量 + FAISS 索引 | 新增向量存储层 | 语义检索能力 |
| GPU NVDEC/Decord 帧提取 | FFmpeg 层面优化 | 帧提取提速 5-10x |
| 增量索引更新 | 索引服务增强 | 局部修改秒级响应 |
| 缓存语义化匹配 | 缓存层升级 | 相似 prompt 命中率提升 |

### Phase 4：前沿探索（长期，依赖模型演进）

| 任务 | 前置条件 |
|------|----------|
| 交错 MRoPE 长视频处理 | core-nexus-ai 支持 Qwen3-VL 256K |
| 分解注意力超长视频 | Vidi2 模型部署 |
| 端侧轻量模型预处理 | 本地模型推理能力 |

---

## 六、关键指标与验证方法

| 指标 | 当前基线 | Phase 1 目标 | Phase 2 目标 |
|------|----------|-------------|-------------|
| 5min 视频分析延迟 | ~15s（VL API） | <2s（索引命中） | <1s |
| 30min 视频分析延迟 | ~60s（VL API） | <5s（索引命中） | <3s |
| VL API 调用次数/任务 | 1-3 次 | 0-1 次 | 0 次（索引完整时） |
| 内存峰值（base64 编码） | 500MB-2GB | <50MB | <10MB |
| 缓存命中率 | ~10%（prompt 敏感） | >60% | >80% |
| 素材库检索精度 | 关键词匹配 | 关键词匹配 | 语义检索（+CLIP） |

---

## 七、总结

核心优化思路：**用结构化索引替代原始视频流，让大模型仅在关键决策点介入。**

与原文档的关键差异：

1. **立足现有代码**：充分利用已有的 `detect_scene_changes()`、`extract_keyframes()`、`result_cache.py` 等能力，串联而非重写
2. **渐进式落地**：Phase 1 仅需新增一个服务 + 一个实体，1-2 周即可见效
3. **补充了原文档缺失的维度**：渐进式分析、后台预处理、流式返回、增量更新、缓存语义化
4. **务实的优先级排序**：先串联现有能力（低成本高收益），再引入新依赖（CLIP/FAISS/Decord）
