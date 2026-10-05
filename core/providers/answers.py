"""Typed decision contract migrated from custom-jev source."""
import json
import re
import math
from core.errors import JevError

def _number(value) -> float | None:
    """模型爱把数字写成字符串；认不出来就给 None，别猜。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if math.isfinite(float(value)) else None
    if isinstance(value, str):
        try:
            n = float(value.strip())
            return n if math.isfinite(n) else None
        except ValueError:
            return None
    return None


def _unit(value) -> float:
    return max(0.0, min(1.0, value))


def _probabilities(raw, keys: tuple) -> dict:
    """{key: 数字} 里只留认得的 key，顺手夹到 0~1。"""
    if not isinstance(raw, dict):
        return {}
    out = {}
    for name in keys:
        value = _number(raw.get(name))
        if value is not None:
            out[name] = _unit(value)
    return out


def _answer_of(question: dict, raw) -> dict | None:
    """一道题的回答 → 跟 OpenRouter 那条路一模一样的形状；不像话就返回 None。

    宁缺勿错：少一道题只是少一行判断，瞎猜的答案会一路带到起草里去。
    """
    kind = question.get("type")
    criteria = question.get("criteria")
    given = raw if isinstance(raw, dict) else {}
    if kind == "noul":
        value = _number(given.get("noul")) if isinstance(raw, dict) else _number(raw)
        return None if value is None else {"type": "noul", "noul": _unit(value)}
    if kind == "choice" and isinstance(criteria, dict):
        choice = given.get("choice") if isinstance(raw, dict) else raw
        choice = str(choice).strip() if choice is not None else ""
        if choice not in criteria:
            return None
        confidence = _number(given.get("confidence"))
        probabilities = _probabilities(given.get("probabilities"), tuple(criteria))
        if not probabilities and confidence is not None:
            probabilities = {choice: _unit(confidence)}  # 没给概率就拿置信度顶上
        answer = {"type": "choice", "choice": choice, "probabilities": probabilities}
        if confidence is not None:
            answer["confidence"] = _unit(confidence)
        return answer
    if kind == "score" and isinstance(criteria, list) and criteria:
        value = _number(given.get("score")) if isinstance(raw, dict) else _number(raw)
        if value is None or value != int(value) or not 0 <= value < len(criteria):
            return None
        last = float(len(criteria) - 1)
        score = float(int(round(max(0.0, min(last, value)))))
        keys = tuple(str(i) for i in range(len(criteria)))
        answer = {"type": "score", "score": score,
                  "probabilities": _probabilities(given.get("probabilities"), keys)}
        confidence = _number(given.get("confidence"))
        if confidence is not None:
            answer["confidence"] = _unit(confidence)
        return answer
    return None


def _answers_of(questions: dict, body: dict) -> dict:
    """响应正文 → answers。一道题都没答成约定格式就算这次判断失败了。"""
    content = _content_of(body)
    try:
        data = json.loads(content)
    except ValueError:
        block = re.search(r"\{.*\}", content, re.S)  # 有的模型爱套一层 ```json
        if block is None:
            raise JevError("判断模型没有回 JSON，检查对面是不是 OpenAI 兼容接口") from None
        try:
            data = json.loads(block.group(0))
        except ValueError:
            raise JevError("判断模型回的 JSON 解析不了") from None
    answers = data.get("answers") if isinstance(data, dict) else None
    if not isinstance(answers, dict):
        raise JevError("判断模型的 JSON 里没有 answers 字段")
    out = {}
    for name, question in questions.items():
        answer = _answer_of(question, answers.get(name))
        if answer is not None:
            out[name] = answer
    if not out:
        raise JevError("判断模型一道题都没按约定格式回答")
    return out


def _content_of(body: dict) -> str:
    """OpenAI 兼容响应里取正文。"""
    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or not choices:
        raise JevError("判断模型没有返回 choices")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):  # 少数服务按 block 回
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    if not isinstance(content, str) or not content.strip():
        finish = choices[0].get("finish_reason") or "?"
        thought = isinstance(message, dict) and (message.get("reasoning")
                                                or message.get("reasoning_content"))
        why = "token 全花在思考上了，换个普通模型或把预算放大" if thought else "模型没给正文"
        raise JevError(f"判断模型返回了空内容（{why}；finish_reason={finish}）")
    return content


def _usage_of(body: dict) -> dict:
    usage = body.get("usage") if isinstance(body, dict) else None
    if not isinstance(usage, dict):
        return {}
    out = {}
    for src, dst in (("prompt_tokens", "input_tokens"), ("completion_tokens", "output_tokens")):
        value = usage.get(src)
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            out[dst] = value
    return out


