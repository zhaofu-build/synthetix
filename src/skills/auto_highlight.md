# auto_highlight

自动分析视频素材，提取精彩片段并合并为集锦。

**所需工具**: list_videos, analyze_video_vl, cut_video, merge_videos

## 执行流程

1. 先调用 list_videos 获取所有素材
2. 对每个素材调用 analyze_video_vl 分析内容，识别高光时刻
3. 根据分析结果，用 cut_video 提取精彩片段（每段5-15秒）
4. 用 merge_videos 合并所有精彩片段

> 注意：片段之间保持节奏感，总时长控制在30-60秒
