from core.errors import JevError
from .openrouter import OpenRouterProvider
from .typesafe import TypeSafeProvider
from .custom_openai import CustomOpenAIProvider
from .custom_typesafe import CustomTypeSafeProvider

DECISION_PROVIDERS = {"openrouter": OpenRouterProvider(), "typesafe": TypeSafeProvider(),
                      "custom_openai": CustomOpenAIProvider(), "custom_typesafe": CustomTypeSafeProvider()}

def get_provider(name):
    try:
        return DECISION_PROVIDERS[name]
    except KeyError:
        raise JevError("未知判断模型来源") from None
