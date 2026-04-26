# Vlog 高光提取
从旅行/日常 Vlog 中提取最精彩的瞬间，制作节奏紧凑的精华视频。
**所需工具**: list_videos, analyze_video_vl, detect_scene_change, detect_silence, cut_video, merge_videos
**适用场景**: 旅行 Vlog、日常记录、活动回顾、派对视频
**参数**: style(节奏: 紧凑/舒缓, 默认紧凑), duration(目标时长, 默认60秒)

## 执行流程

1. 列出所有素材 list_videos
2. 多信号分析：
   - analyze_video_vl 视觉分析（人物表情、景色壮丽度、动作幅度）
   - detect_scene_change 场景切换密度（高频区域通常更精彩）
   - detect_silence 静音检测（有音乐/笑声/欢呼声的段更有趣）
3. 综合评分筛选高光片段：
   - 视觉丰富度 50%
   - 音频活跃度 30%
   - 场景多样性 20%
4. 按 style 调整剪辑节奏：
   - 紧凑：每片段 2-4 秒，快速转场
   - 舒缓：每片段 4-8 秒，淡入淡出
5. 使用 cut_video + merge_videos 组合

## 剪辑策略

- 开头用最震撼/有趣的画面
- 保持画面多样性（不连续使用同一场景）
- 音乐节拍点对齐画面切换
- 人物表情特写优于空镜头
