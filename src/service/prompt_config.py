def keywords_prompt(creative):
    return f"""
    根据下面的文案生成2个高度相关的视频搜索关键词：
    {creative}
    要求：
    1. 搜索词以,分隔
    2. 每个搜索词应由 1-3 个单词组成，始终添加视频的主要主题。
    3. 搜索词只能返回关键词，不要标题和解释性说明
    4. 仅使用英文搜索词进行回复。
    返回示例:
    search term 1, "search term 2,  search term 3
    注意，必须使用英语生成视频搜索词;不接受中文。
    """


def clip_prompt(creative, source_infos, duration):
    return f"""
        {{
      "task": "根据给出的source_materials给出剪辑如response_example的信息",
      "requirements": {{
        "input": {{
          "creative_script": "{creative}",
          "source_materials": "{source_infos}"
        }},
        "output": {{
          "format": "strict_json",
          "critical_rules": [
            "⚠️ 绝对时间约束: start_time全部等于00:00:00.000" 
            "⚠️ 绝对时间约束: start_time全部等于00:00:00.000" 
            "⚠️ 绝对时间约束: end_time < duration",
            "⏱ 总时长控制: 所有片段的(end_time)累计必须等于{duration}秒",
            "🔒 源数据锁定: 必须完整保留source_name的原始哈希值（如3851984）"
            "⚠️ 与主题creative_script无关的source_info不要反回"
          ],
          "technical_specs": [
            "时间格式: 时间码格式强制为HH:MM:SS.mmm（例：00:00:07.500）",
            "帧率兼容: 不同帧率素材转换需保持时间码连续性",
            "安全间隔: 相邻片段至少保留10帧重叠（如24fps需≥0.42秒）"
          ],
          "quality_standards": [
            "转场匹配: dissolve仅限场景渐变，cut用于硬切/静帧",
            "优先级: 情感匹配度 > 构图质量 > 运动连贯性"          
            ]
        }},
        "processing_logic": [
          "STEP 1: 语义分析 - 解析文案中的关键词/情感/节奏",
          "STEP 2: 时长校验 - 验证所有end_time ≤ duration",
          "STEP 3: 节奏规划 - 按『建立-发展-高潮-收尾』结构分配时段",
      }},
      "response_example":     
      [
         {{
          "id": 1,
          "duration": 15,
          "start_time": "00:00:00.000",
          "end_time": "00:00:12.000",
          "transition": "dissolve"
        }},
        {{
          "id": 2,
          "duration": 20,
          "start_time": "00:00:00.000",
          "end_time": "00:00:18.000",
          "transition": "cut"
        }}
      ]
    }}
        """


def llm_translate(text, lang="zh"):
    return f"""请将<source>中的原文内容按字面意思翻译到{lang}，然后只输出译文，不要添加任何说明或引导词。

    **格式要求：**
    - 按行翻译原文，并生成该行对应的译文，确保原文行和译文行中的每个单词相互对应。
    - 有几行原文，必须生成几行译文。

    **内容要求：**
    - 翻译必须精简短小，避免长句。
    - 如果原文无法翻译，请返回空行，不得添加“无意义语句或不可翻译”等任何提示语。
    - 只输出译文即可，禁止输出任何原文。

    **执行细节：**
    - 如果某行原文很短，在翻译后也仍然要保留该行，不得与上一行或下一行合并。
    - 原文换行处字符相对应的译文字符也必须换行。
    - 严格按照字面意思翻译，不要解释或回答原文内容。

    **最终目标：**
    - 提供格式与原文完全一致的高质量翻译结果。

    <source>{text}</source>

    译文:
    """


prompt_zh_srt = """请将<source>中的srt字幕格式内容翻译到{lang}，然后只输出译文，不要添加任何说明或引导词：

注意以下要求：
1. **只翻译**字幕文本内容，不翻译字幕的行号和时间戳。
2. **必须保证**翻译后的译文格式为有效的 srt字幕。
3. **确保**翻译后的字幕数量和原始字幕完全一致，每一条字幕对应原始字幕中的一条。
4. **保持时间戳的原样**，只翻译幕文本内容。
5. 如果遇到无法翻译的情况，直接将原文本内容返回，不要报错，不要道歉。

以下是需要翻译的 srt 字幕内容：

<source>[TEXT]</source>

译文:
"""
