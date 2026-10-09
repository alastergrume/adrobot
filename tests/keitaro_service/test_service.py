"""The fake Keitaro service answers like the Keitaro Admin API."""

import json

import pytest
from fastapi.testclient import TestClient

from tests.keitaro_service import seed_test_data
from tests.keitaro_service.app import create_app
from tests.keitaro_service.store import KeitaroStore

API_KEY = "test-api-key"


@pytest.fixture
def service():
    return TestClient(create_app(store=KeitaroStore(None), api_key=API_KEY))


@pytest.fixture
def api(service):
    service.headers["Api-Key"] = API_KEY
    return service


def test_api_key_is_required(service):
    assert service.get("/admin_api/v1/campaigns").status_code == 401
    assert service.get("/admin_api/v1/campaigns", headers={"Api-Key": "wrong"}).status_code == 401


def test_reads_test_data(api):
    assert [c["name"] for c in api.get("/admin_api/v1/campaigns").json()] == ["campaign 2"]
    streams = api.get("/admin_api/v1/campaigns/93212/streams").json()
    assert [s["name"] for s in streams] == ["Flow 1", "Flow 2"]
    assert [(o["offer_id"], o["share"]) for o in streams[1]["offers"]] == [(3749, 33), (3717, 33), (11111, 34)]
    assert len(api.get("/admin_api/v1/offers").json()) == 8
    assert api.get("/admin_api/v1/groups", params={"type": "campaigns"}).json()[0]["name"] == "FORTESTS"
    assert api.get("/admin_api/v1/domains").json()[0]["name"] == "in.posdk.xyz"
    assert api.get("/admin_api/v1/traffic_sources").json()[0]["name"] == "FORTESTS"


def test_create_campaign_and_streams(api):
    campaign = api.post("/admin_api/v1/campaigns", json={"name": "new", "alias": "abc123"}).json()
    stream = api.post(
        "/admin_api/v1/streams",
        json={"campaign_id": campaign["id"], "name": "Flow", "offers": [{"offer_id": 3749, "share": 100}]},
    ).json()
    assert stream["campaign_id"] == campaign["id"] and stream["position"] == 1

    updated = api.put(f"/admin_api/v1/streams/{stream['id']}", json={"offers": [{"offer_id": 3717, "share": 100}]}).json()
    assert [o["offer_id"] for o in updated["offers"]] == [3717]


def test_errors(api):
    assert api.get("/admin_api/v1/campaigns/1").status_code == 404
    response = api.put("/admin_api/v1/streams/564221", json={"offers": [{"offer_id": 1, "share": 100}]})
    assert response.status_code == 422
    assert "offer 1 not found" in response.json()["error"]


def test_admin_page_changes_data(service):
    page = service.get("/admin/")
    assert page.status_code == 200 and "campaign 2" in page.text
    assert service.get("/static/css/style.css").status_code == 200

    response = service.post("/admin/streams/564221/offers/3749/delete", follow_redirects=False)
    assert response.status_code == 303
    stream = service.app.state.store.get_stream(564221)
    assert [o["offer_id"] for o in stream["offers"]] == [3717, 11111]

    service.post("/admin/reset")
    assert len(service.app.state.store.get_stream(564221)["offers"]) == 3


def test_seed_script(tmp_path):
    path = tmp_path / "keitaro.json"
    assert seed_test_data.main(["--path", str(path)]) == 0
    assert json.loads(path.read_text(encoding="utf-8"))["campaigns"][0]["name"] == "campaign 2"

    store = KeitaroStore(path)
    store.delete_stream_offer(564221, 3749)
    seed_test_data.main(["--path", str(path), "--if-empty"])  # keeps the changed data
    assert len(store.get_stream(564221)["offers"]) == 2

    seed_test_data.main(["--path", str(path)])  # reset while the store is in use
    assert len(store.get_stream(564221)["offers"]) == 3
