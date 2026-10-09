"""Interface of the Keitaro Admin API used by the application.

Objects are plain dicts in the same shape as the Admin API returns them,
so the real and the fake client are interchangeable.
"""

from abc import ABC, abstractmethod
from typing import Any

JSON = dict[str, Any]


class KeitaroError(Exception):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class KeitaroClient(ABC):
    @abstractmethod
    def list_campaigns(self) -> list[JSON]: ...

    @abstractmethod
    def get_campaign(self, campaign_id: int) -> JSON: ...

    @abstractmethod
    def create_campaign(self, payload: JSON) -> JSON: ...

    @abstractmethod
    def list_streams(self, campaign_id: int) -> list[JSON]: ...

    @abstractmethod
    def create_stream(self, payload: JSON) -> JSON: ...

    @abstractmethod
    def update_stream(self, stream_id: int, payload: JSON) -> JSON: ...

    @abstractmethod
    def list_offers(self) -> list[JSON]: ...

    @abstractmethod
    def list_domains(self) -> list[JSON]: ...

    @abstractmethod
    def list_campaign_groups(self) -> list[JSON]: ...

    @abstractmethod
    def list_traffic_sources(self) -> list[JSON]: ...
