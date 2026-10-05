import urllib.request
import urllib.error
import socket
from core.errors import JevError
from core.providers import OPENROUTER_DECISIONS, OPENROUTER_KEY_URL
from .base import DecisionProvider
from .transport import _post_json, _error_body

def _check_openrouter_key(key: str, timeout: float) -> None:
    """免费的 auth/key 探测：401/403 说明 key 不对，别的错（超时/断网）也如实上报。
    列表本身是写死的，key 对不对只有靠它才知道，别等第一次判断才暴露。"""
    req = urllib.request.Request(OPENROUTER_KEY_URL,
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        hint = {401: "密钥被拒", 403: "没有权限"}.get(exc.code, _error_body(exc)[:200])
        raise JevError(f"取模型列表 HTTP {exc.code}: {hint}") from None
    except (TimeoutError, socket.timeout):
        raise JevError(f"取模型列表请求超时（{timeout}s）") from None
    except urllib.error.URLError as exc:
        raise JevError(
            "取模型列表失败：无法连接服务") from None



class OpenRouterProvider(DecisionProvider):
    def ask(self, state, questions, key, model, timeout, base_url=None):
        body = _post_json(OPENROUTER_DECISIONS, key, {"model": model, "state": state, "questions": questions}, timeout)
        if not isinstance(body, dict) or not isinstance(body.get("answers"), dict):
            raise JevError("Jev 返回格式异常：没有 answers")
        return body

    def list_models(self, key, timeout, base_url=None):
        _check_openrouter_key(key, timeout)
        return ["~typesafe/jev-latest", "typesafe/jev-1.13"]
