import json
from core.errors import JevError, _fail
from .base import DecisionProvider
from .transport import _norm_base
from .answers import _answers_of, _usage_of

_CUSTOM_SYSTEM = (
    "You are a decision model. You get a conversation and a set of typed questions about it. "
    "Answer every question. Reply with one JSON object and nothing else:\n"
    '{"answers": {"<question name>": <answer>}}\n'
    "Answer shape depends on the question's type field:\n"
    '- noul: {"noul": <0~1>} - probability that the statement in the instructions is true.\n'
    '- choice: {"choice": "<criteria key>", "confidence": <0~1>, "probabilities": '
    '{"<criteria key>": <0~1>}} - probabilities over every criteria key.\n'
    '- score: {"score": <integer>, "confidence": <0~1>, "probabilities": '
    '{"<criteria index>": <0~1>}} - score is the 0-based index of the matching criteria '
    "entry; probabilities are over every index.\n"
    "Weigh the whole thread, not the last line alone. Follow each question's instructions and "
    "criteria strictly, and use the criteria keys exactly as given. No prose, no code fences."
)



class CustomOpenAIProvider(DecisionProvider):
    def ask(self, state, questions, key, model, timeout, base_url=None):
        import openai
        base = _norm_base(base_url)
        try:
            with openai.OpenAI(base_url=base, api_key=key, timeout=timeout, max_retries=1) as client:
                response = client.chat.completions.create(model=model, temperature=0, max_tokens=2000, stream=False, messages=[
                    {"role": "system", "content": _CUSTOM_SYSTEM},
                    {"role": "user", "content": json.dumps({"state": state, "questions": questions}, ensure_ascii=False)}])
            body = response.model_dump()
            return {"answers": _answers_of(questions, body), "usage": _usage_of(body)}
        except Exception as exc:
            _fail(exc, "自定义判断")

    def list_models(self, key, timeout, base_url=None):
        import openai
        base = _norm_base(base_url)
        try:
            with openai.OpenAI(base_url=base, api_key=key, timeout=timeout, max_retries=1) as client:
                ids = sorted({m.id for m in client.models.list() if m.id})
            if not ids:
                raise JevError("模型列表为空")
            return ids
        except Exception as exc:
            _fail(exc, "取模型列表")
