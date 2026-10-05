from core.errors import JevError, _fail
from core.providers import TYPESAFE_BASE
from .base import DecisionProvider

def _answer(answer) -> dict:
    """SDK 的答案对象 → OpenRouter 那条路 JSON 出来的同一个形状。"""
    if answer.type == "noul":
        return {"type": "noul", "noul": answer.noul}
    if answer.type == "choice":
        return {"type": "choice", "choice": answer.choice, "confidence": answer.confidence,
                "probabilities": dict(answer.probabilities)}
    # score：SDK 把概率的 key 转成了 int，这里转回字符串，跟 JSON 那条路对齐
    return {"type": "score", "score": answer.score, "confidence": answer.confidence,
            "probabilities": {str(k): v for k, v in answer.probabilities.items()}}


def _ask_typesafe(state: dict, questions: dict, key: str, model: str, timeout: float,
                  base_url: str | None = None) -> dict:
    """官方 typesafe_sdk。questions 原样传：core/questions.py 里那几个 dict 本身就是 SDK 的
    NoulModel / ChoiceModel / ScoreModel（SDK 的 normalize_questions 认 dict），不用再包一层对象。
    重试用 RetryPolicy 的默认值——它本来就重试 408/429/5xx（含 529）并退避。
    base_url 只有自定义来源才给：TypeSafe 协议的镜像（TeamoRouter 之类）走这里。"""
    import typesafe_sdk

    base = base_url or TYPESAFE_BASE
    try:
        with typesafe_sdk.TypeSafeClient(api_key=key, base_url=base, model=model,
                                         timeout=timeout) as client:
            result = client.system_one(state, questions, model=model)
    except Exception as exc:
        _fail(exc, "Jev 判断")
    return {
        "answers": {name: _answer(a) for name, a in result.answers.items()},
        "usage": {"input_tokens": result.usage.input_tokens,
                  "output_tokens": result.usage.output_tokens},
    }



class TypeSafeProvider(DecisionProvider):
    def address(self, base_url):
        return TYPESAFE_BASE

    def ask(self, state, questions, key, model, timeout, base_url=None):
        return _ask_typesafe(state, questions, key, model, timeout, self.address(base_url))

    def list_models(self, key, timeout, base_url=None):
        import typesafe_sdk
        try:
            with typesafe_sdk.TypeSafeClient(api_key=key, base_url=self.address(base_url), timeout=timeout) as client:
                ids = sorted({m.name for m in client.models.list().models})
            if not ids:
                raise JevError("模型列表为空；可以手填模型 id")
            return ids
        except Exception as exc:
            _fail(exc, "取模型列表（此来源可能仅支持手填模型 id）")
