# smart_short_video

从素材中智能制作一个30秒短视频。

**所需工具**: list_videos, analyze_video_vl, smart_clip, add_subtitle, add_audio

## 执行流程

1. 调用 list_videos 获取项目素材
2. 调用 analyze_video_vl 分析素材内容
3. 根据素材内容规划30秒短视频的剪辑方案
4. 使用 smart_clip 或逐个 cut_video 提取片段
5. 使用 merge_videos 合并片段
6. 添加字幕和背景音乐
