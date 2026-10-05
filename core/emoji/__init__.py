"""Local semantics are hints; conversational intent is a separate optional stage."""
import re

SEMANTICS = {"😀": "笑脸/开心", "😂": "笑哭/可能调侃", "🤣": "大笑", "👍": "赞同/支持",
             "😭": "哭泣/可能夸张", "😅": "苦笑/尴尬", "🙄": "翻白眼/无语", "😮": "惊讶",
             "😡": "生气", "❤️": "爱心/支持", "🙏": "感谢/请求", "🤔": "思考/疑问",
             "[捂脸]": "捂脸/尴尬/无奈", "[笑哭]": "笑哭/调侃", "[强]": "支持", "[流泪]": "难过",
             "[微笑]": "微笑（语境可能影响含义）", "[狗头]": "调侃/反讽提示", "[旺柴]": "调侃提示"}

def local_semantics(text):
    return "；".join(meaning for symbol, meaning in SEMANTICS.items() if symbol in text)

def only_emoji(text):
    rest = text
    for symbol in SEMANTICS:
        rest = rest.replace(symbol, "")
    rest = re.sub(r"[\U0001f000-\U0001faff\u2600-\u27bf\ufe0f\u200d\s]", "", rest)
    return bool(text.strip()) and not rest

