from .typesafe import TypeSafeProvider
from .transport import _norm_base

class CustomTypeSafeProvider(TypeSafeProvider):
    def address(self, base_url):
        return _norm_base(base_url)
