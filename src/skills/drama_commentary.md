# 短剧解说剪辑
对影视剧/短视频素材进行解说式二次创作，提取关键情节片段并配上解说文案。
**所需工具**: transcribe_video, analyze_video_vl, cut_video, merge_videos, add_subtitle, generate_tts
**适用场景**: 影视解说、短剧二创、故事讲述、内容摘要
**参数**: narration_style(解说风格: 悬疑/幽默/情感, 默认悬疑), duration(目标时长, 默认90秒)

## 执行流程

1. 使用 transcribe_video 获取原始对白
2. 使用 analyze_video_vl 分析画面内容
3. 提取关键情节节点：
   - 故事开头（设定场景）
   - 冲突/转折点
   - 高潮片段
   - 结局/悬念
4. 使用 cut_video 提取每个情节的关键片段
5. 生成解说文案（基于情节提取结果，用 narration_style 风格编写）
6. 使用 generate_tts 生成解说语音
7. 使用 merge_videos 合并片段 + 解说音频
8. 使用 add_subtitle 添加字幕

## 剪辑策略

- 每个情节片段 3-8 秒，保持紧凑
- 解说文案要简洁有力，避免冗长描述
- 关键转折处留足悬念
- 配音节奏与画面节奏匹配
- 结尾设置悬念或总结
