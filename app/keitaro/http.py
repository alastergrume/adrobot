"""Keitaro Admin API client over HTTP.

Base path: <tracker>/admin_api/v1, authentication: the "Api-Key" header.
"""

import time

import httpx

from app.keitaro.base import JSON, KeitaroClient, KeitaroError

API_PATH = "/admin_api/v1"
OFFERS_CACHE_TTL_S = 30  # offer search runs on every keystroke


class HttpKeitaroClient(KeitaroClient):
    def __init__(self, base_url: str, api_key: str, timeout_s: float = 20.0, http_client: httpx.Client | None = None):
        """``http_client`` lets tests plug in a client bound to the fake Keitaro service."""
        self._configured = bool(base_url and api_key)
        base_url = base_url.rstrip("/")
        if not base_url.endswith(API_PATH):
            base_url += API_PATH
        self._http = http_client or httpx.Client(
            base_url=base_url,
            headers={"Api-Key": api_key, "Accept": "application/json"},
            timeout=timeout_s,
        )
        self._offers: list[JSON] | None = None
        self._offers_loaded_at = 0.0

    def _request(self, method: str, path: str, **kwargs):
        if not self._configured:
            raise KeitaroError("Keitaro is not configured: set KEITARO_URL and KEITARO_API_KEY in app/configs/.env")
        try:
            response = self._http.request(method, path, **kwargs)
        except httpx.HTTPError as error:
            raise KeitaroError(f"Keitaro is unreachable: {error}") from error
        if response.status_code >= 400:
            raise KeitaroError(
                f"Keitaro {method} {path} failed: {response.status_code} {response.text[:300]}",
                status_code=response.status_code,
            )
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError as error:
            raise KeitaroError(f"Keitaro {method} {path} returned a non-JSON response") from error

    def list_campaigns(self) -> list[JSON]:
        return self._request("GET", "/campaigns")

    def get_campaign(self, campaign_id: int) -> JSON:
        return self._request("GET", f"/campaigns/{campaign_id}")

    def create_campaign(self, payload: JSON) -> JSON:
        return self._request("POST", "/campaigns", json=payload)

    def list_streams(self, campaign_id: int) -> list[JSON]:
        return self._request("GET", f"/campaigns/{campaign_id}/streams")

    def create_stream(self, payload: JSON) -> JSON:
        return self._request("POST", "/streams", json=payload)

    def update_stream(self, stream_id: int, payload: JSON) -> JSON:
        return self._request("PUT", f"/streams/{stream_id}", json=payload)

    def list_offers(self) -> list[JSON]:
        if self._offers is None or time.monotonic() - self._offers_loaded_at > OFFERS_CACHE_TTL_S:
            self._offers = self._request("GET", "/offers")
            self._offers_loaded_at = time.monotonic()
        return self._offers

    def list_domains(self) -> list[JSON]:
        return self._request("GET", "/domains")

    def list_campaign_groups(self) -> list[JSON]:
        return self._request("GET", "/groups", params={"type": "campaigns"})

    def list_traffic_sources(self) -> list[JSON]:
        return self._request("GET", "/traffic_sources")
