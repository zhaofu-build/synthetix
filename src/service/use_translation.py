import os
# 设置translators库的区域环境变量，避免SSL证书验证问题
os.environ["translators_default_region"] = "EN"

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


def translator_build(messages, to_language='zh', translator_server='bing'):
    # llm大模型翻译
    if translator_server == "ollama":
        from src.service import use_langchain_llm
        from prompt_config import llm_translate
        return use_langchain_llm.generate_response(
            messages=[{"role": "user", "content": llm_translate}]
        )
    # 联网翻译
    return translator_response(messages, to_language, translator_server)


if __name__ == '__main__':
    # response = translator_response('你好，最近怎么样？ ', 'en', 'youdao')
    # print(response)
    response1 = translator_build('how are you?', 'zh', 'bing')
    print(response1)
    # response = batch_translate(['Hello', 'how are you?'], 'zh', 'bing')
    # print(response)
