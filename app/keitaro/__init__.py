from functools import lru_cache

from app.configs import keitaro_settings
from app.keitaro.base import KeitaroClient, KeitaroError
from app.keitaro.http import HttpKeitaroClient

__all__ = ["KeitaroClient", "KeitaroError", "HttpKeitaroClient", "get_keitaro"]


@lru_cache
def get_keitaro() -> KeitaroClient:
    return HttpKeitaroClient(
        keitaro_settings.url,
        keitaro_settings.api_key.get_secret_value(),
        keitaro_settings.timeout_s,
    )
