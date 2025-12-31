import translators as ts

import config


# 搜索引擎
# bing - 必应
# sogou - 搜狗
# alibaba 阿里云
# caiyun - 彩云小译
# deepl -DeepL

# 支持语言
# zh - 中文
# ar - 阿拉伯语
# de - 德语
# en - 英语
# es - 西班牙语
# fr - 法语
# ja - 日语
# ko - 韩语
# ru - 俄语
# vi - 越南语
# pt - 葡萄牙语
# id - 印度尼西亚语

# 单句翻译
def translator_response(messages, to_language='zh', translator_server='bing'):
    return ts.translate_text(query_text=messages, translator=translator_server, from_language='auto',
                             to_language=to_language)


# 批量翻译
def batch_translate(texts, to_lang='zh', translator_server='bing'):
    translations = []
    for text in texts:
        translation = ts.translate_text(query_text=text, translator=translator_server, from_language='auto',
                                        to_language=to_lang)
        translations.append(translation)
    return translations


def ollama_translate(text, lang="zh"):
    prompt_zh = f"""请将<source>中的原文内容按字面意思翻译到{lang}，然后只输出译文，不要添加任何说明或引导词。

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
    prompt_en = """Please translate the original text in <source> literally to {lang}, and then output only the 
        translated text without adding any notes or leading words. 

    **Format Requirements:**
    - Translate the original text line by line and generate the translation corresponding to that line, making sure that each word in the original line and the translated line corresponds to each other.
    - If there are several lines of original text, several lines of translation must be generated.

    **Content requirements:**
    - Translations must be concise and short, avoiding long sentences.
    - If the original text cannot be translated, please return to an empty line, and do not add any hints such as "meaningless statement or untranslatable", etc. Only the translated text can be output, and it is forbidden to output the translated text.
    - Only the translation can be output, and it is forbidden to output any original text.

    **Execution details:**
    - If a line is very short in the original text, it should be retained after translation, and should not be merged with the previous or next line.
    - The characters corresponding to the characters in the translation at the line breaks in the original text must also be line breaks.
    - Translate strictly literally, without interpreting or answering the content of the original text.

    **End goal:**
    - Provide high-quality translations that are formatted exactly like the original.

    <source>[TEXT]</source>

    Translation:

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
    prompt_en_srt = """Please translate the content of srt subtitle format in <source> to {lang}, and then output only the translated text without adding any description or guide words:

    Note the following requirements:
    1. **Translate **subtitle text content only, do not translate subtitle line numbers and timestamps.
    2. **Must ensure that **the translated translation format is a valid srt subtitle.
    3. **Must ensure that the number of **translated subtitles is exactly the same as the original subtitles, and that each subtitle corresponds to one of the original subtitles.
    4. **Keep the timestamps as they are** and translate only the content of the subtitles.
    5. If you can't translate the subtitle, you can return the original text directly without reporting any error.

    The following is the content of the srt subtitle to be translated:

    <source>[TEXT]</source>

    Translation:"""
    return use_ollama.ollama_generate(config.ollama_translate_model, prompt_zh)


def translator_build(messages, to_language='zh', translator_server='bing'):
    # 本地大模型翻译
    if translator_server == "ollama":
        return ollama_translate(messages, to_language)
    # 联网翻译
    return translator_response(messages, to_language, translator_server)


if __name__ == '__main__':
    # response = translator_response('你好，最近怎么样？ ', 'en', 'youdao')
    # print(response)
    response1 = translator_build('how are you?', 'zh', 'bing')
    print(response1)
    # response = batch_translate(['Hello', 'how are you?'], 'zh', 'bing')
    # print(response)
