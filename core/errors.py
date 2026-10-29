"""Safe, shared model errors. Never echo upstream request/response bodies."""
import os
from contextlib import contextmanager
from contextvars import ContextVar

_task_keys = ContextVar("task_keys", default=None)

@contextmanager
def credential_snapshot(keys):
    token = _task_keys.set(dict(keys))
    try:
        yield
    finally:
        _task_keys.reset(token)

from typing import NoReturn
from core.providers import ENV_VARS, JEV_ENV, LEGACY

class JevError(Exception):
    def __init__(self, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def redact_secrets(text: str) -> str:
    """Strip every live key from any string before print or disk write."""
    if not isinstance(text, str):
        text = str(text)
    for key in (_task_keys.get() or {}).values():
        if key:
            text = text.replace(key, "[REDACTED]")
    for env in ENV_VARS:
        key = os.environ.get(env) or ""
        if key:
            text = text.replace(key, "[REDACTED]")
    return text


def _status_of(exc: Exception) -> int | None:
    """各家 SDK 放 HTTP 状态码的属性名不一样：openai/anthropic 是 status_code，
    google-genai 是 code（它的 status 是 'NOT_FOUND' 这种字符串），typesafe 是 status。"""
    for name in ("status_code", "code", "status"):
        value = getattr(exc, name, None)
        if isinstance(value, int):
            return value
    return None


def _fail(exc: Exception, what: str) -> NoReturn:
    """SDK 抛的异常 → 一句人话的 JevError。消息过脱敏，绝不把 key 带出来。"""
    if isinstance(exc, JevError):
        raise exc
    status = _status_of(exc)
    hint = {401: "密钥被拒", 403: "没有权限", 404: "模型或地址不对", 422: "请求被拒",
            429: "被限流", 529: "服务过载"}.get(status, "")
    detail = {"APITimeoutError": "网络超时", "APIConnectionError": "无法连接服务",
              "TimeoutError": "网络超时"}.get(type(exc).__name__, type(exc).__name__)
    head = f"{what} HTTP {status}" if status else f"{what}失败"
    raise JevError(f"{head}: {hint or detail or type(exc).__name__}", status) from None


def _api_key(env: str = JEV_ENV) -> str:
    """两把 key 之一（JEV_API_KEY / LLM_API_KEY）。新名字空着就退回老名字，老用户不用重填。"""
    snapshot = _task_keys.get()
    if snapshot is not None and env in snapshot:
        key = snapshot[env]
        if not key:
            raise JevError("本次任务未配置模型密钥")
        return key
    key = ((os.environ.get(env) or "").strip()
           or (os.environ.get(LEGACY.get(env, "")) or "").strip())
    if not key:
        raise JevError(
            f"{env} is not set. Export it in the environment; "
            "do not put the key in a file."
        )
    return key


