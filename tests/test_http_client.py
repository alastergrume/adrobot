"""The HTTP client sends the right requests (checked with a mocked transport)."""

import httpx
import pytest

from app.keitaro import HttpKeitaroClient, KeitaroError


def make_client(handler, url="https://tracker.example"):
    client = HttpKeitaroClient(url, "secret-key")
    client._http = httpx.Client(
        base_url=client._http.base_url, headers=client._http.headers, transport=httpx.MockTransport(handler)
    )
    return client


def test_requests_use_api_path_and_key():
    seen = []

    def handler(request):
        seen.append((request.method, request.url.path, request.headers["Api-Key"], request.content))
        return httpx.Response(200, json={"id": 564221})

    client = make_client(handler)
    client.update_stream(564221, {"offers": [{"offer_id": 3749, "share": 100, "state": "active"}]})
    method, path, key, body = seen[0]
    assert (method, path, key) == ("PUT", "/admin_api/v1/streams/564221", "secret-key")
    assert b'"offer_id":3749' in body.replace(b" ", b"")


def test_url_with_api_path_is_not_doubled():
    client = HttpKeitaroClient("https://tracker.example/admin_api/v1/", "key")
    assert str(client._http.base_url).rstrip("/") == "https://tracker.example/admin_api/v1"


def test_errors_are_wrapped():
    client = make_client(lambda request: httpx.Response(401, text="Unauthorized"))
    with pytest.raises(KeitaroError) as error:
        client.list_campaigns()
    assert error.value.status_code == 401


def test_offers_are_cached():
    calls = []

    def handler(request):
        calls.append(request.url.path)
        return httpx.Response(200, json=[{"id": 1, "name": "Offer"}])

    client = make_client(handler)
    client.list_offers()
    client.list_offers()
    assert calls == ["/admin_api/v1/offers"]


def test_not_configured_client_explains_what_to_set():
    client = HttpKeitaroClient("", "")
    with pytest.raises(KeitaroError) as error:
        client.list_campaigns()
    assert "KEITARO_URL" in str(error.value)
