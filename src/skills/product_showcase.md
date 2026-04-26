# 产品展示视频
制作突出产品功能和亮点的展示视频，适合电商和营销场景。
**所需工具**: list_videos, analyze_video_vl, cut_video, merge_videos, add_subtitle
**适用场景**: 产品发布、电商详情页、社交媒体推广、品牌宣传
**参数**: style(风格: 简约/动感/高端, 默认简约), duration(时长, 默认45秒), platform(平台: douyin/bilibili/xiaohongshu)

## 执行流程

1. 列出项目素材 list_videos
2. 使用 analyze_video_vl 分析每个素材的画面内容
3. 筛选最佳展示片段：
   - 产品整体外观
   - 核心功能演示
   - 使用场景展示
   - 细节特写
4. 按产品展示逻辑排序：外观 → 功能 → 场景 → 细节
5. 使用 cut_video 精确提取每个片段
6. 使用 merge_videos 合并片段，添加转场
7. 可选：使用 add_subtitle 添加卖点字幕

## 剪辑策略

- 开头 3 秒必须抓住注意力（最佳角度或最亮点）
- 每个功能展示不超过 5 秒
- 保持画面稳定，避免晃动素材
- 结尾展示品牌或购买信息
