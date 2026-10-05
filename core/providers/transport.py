"""Bounded HTTP transport for the non-SDK Decisions endpoint."""
import json
import socket
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from core.errors import JevError
from core.providers import JEV_ENV
MAX_RETRIES = 2

def _error_body(exc: urllib.error.HTTPError) -> str:
    return "服务返回错误；响应正文已隐藏"


def _post_json(url: str, key: str, payload: dict, timeout: float) -> dict:
    """POST 一份 JSON，429/529 退避重试 3 次；出错转成一句人话（消息过脱敏）。

    两条自己拼 HTTP 的路（OpenRouter / 自定义来源）共用这一份。
    """
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    last_status: int | None = None
    for attempt in range(MAX_RETRIES + 1):
        req = urllib.request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json; charset=utf-8",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_status = exc.code
            if last_status in (429, 529) and attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            readable = {
                401: f"Jev HTTP 401: API key rejected. Check {JEV_ENV}.",
                403: "Jev HTTP 403: this key has no access to the model.",
                404: "Jev HTTP 404: endpoint not found; check the Base URL.",
                422: "Jev HTTP 422: request body rejected by the provider.",
                429: f"Jev HTTP 429: rate limited after {MAX_RETRIES} retries.",
                529: f"Jev HTTP 529: provider overloaded after {MAX_RETRIES} retries.",
            }.get(last_status, f"Jev HTTP {last_status}: provider request failed.")
            raise JevError(readable, last_status) from None
        except (TimeoutError, socket.timeout) as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            raise JevError(f"Jev request timed out after {timeout}s") from exc
        except urllib.error.URLError as exc:
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            raise JevError("Jev 请求无法连接服务") from None
        except (ValueError, UnicodeError):
            raise JevError("Jev 返回格式异常：不是 JSON") from None

    raise JevError(f"Jev HTTP {last_status}: provider request failed.", last_status)


def _norm_base(base_url: str | None) -> str:
    """设置页填的 Base URL → 可以直接拼路径的前缀。跟起草那边一样，一般要带 /v1。"""
    base = (base_url or "").strip().rstrip("/")
    if not base:
        raise JevError("自定义判断来源要先填 Base URL")
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise JevError("Base URL 必须是无密钥、无查询参数的 http(s) 服务地址")
    return base


