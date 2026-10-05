from core.errors import JevError
from .typesafe import TypeSafeProvider
from .transport import _norm_base

class CustomTypeSafeProvider(TypeSafeProvider):
    def address(self, base_url):
        return _norm_base(base_url)

    def list_models(self, key, timeout, base_url=None):
        try:
            return super().list_models(key, timeout, base_url)
        except JevError as exc:
            raise JevError(
                "这个来源的模型列表不一定有，手填模型 id 即可（TeamoRouter 填 jev）"
            ) from exc
