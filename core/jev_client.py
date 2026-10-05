"""Stable public facade; providers own protocols and Engine owns orchestration."""
from core.errors import JevError, redact_secrets, _api_key, _fail
from core.providers import JEV_ENV, JEV_PROVIDERS
from core.providers.registry import get_provider

def ask(state, questions, timeout=20, provider="openrouter", model=None, base_url=None):
    adapter = get_provider(provider)
    model = model or JEV_PROVIDERS[provider].default
    if not model:
        raise JevError("自定义判断来源要先填模型 id")
    return adapter.ask(state, questions, _api_key(JEV_ENV), model, timeout, base_url)

def list_models(provider, key, timeout=10, base_url=None):
    return get_provider(provider).list_models(key, timeout, base_url)
