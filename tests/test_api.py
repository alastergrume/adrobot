import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from app.db import get_db
from app.keitaro import get_keitaro
from app.main import app


@pytest.fixture
def client(engine, keitaro):
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_db():
        session = Session()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_keitaro] = lambda: keitaro
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def shares(campaign, stream_name="Flow 2"):
    stream = next(s for s in campaign["streams"] if s["name"] == stream_name)
    return {o["offer_id"]: o["share"] for o in stream["offers"] if o["status"] == "active"}, stream


def test_offer_search(client):
    found = client.get("/api/offers", params={"q": "oxys"}).json()
    assert found == [{"id": 11112, "name": "11112 Oxys [BEAUTY-CL-BE_0155] [pl es -]"}]
    assert client.get("/api/offers", params={"q": "3749"}).json()[0]["id"] == 3749


def test_editor_flow(client):
    campaign = client.post("/api/campaigns/import", json={"keitaro_id": 93212}).json()
    current, stream = shares(campaign)
    assert current == {3749: 33, 3717: 33, 11111: 34}

    assert client.post(f"/api/streams/{stream['id']}/offers", json={"offer_id": 11112}).status_code == 201
    campaign = client.get(f"/api/campaigns/{campaign['id']}").json()
    current, stream = shares(campaign)
    assert current == {3749: 25, 3717: 25, 11111: 25, 11112: 25}
    assert stream["is_dirty"]

    assert client.post(f"/api/streams/{stream['id']}/push").json() == {"ok": True}
    campaign = client.get(f"/api/campaigns/{campaign['id']}").json()
    assert not shares(campaign)[1]["is_dirty"]


def test_errors_are_readable(client):
    campaign = client.post("/api/campaigns/import", json={"keitaro_id": 93212}).json()
    stream = shares(campaign)[1]

    response = client.post(f"/api/streams/{stream['id']}/offers", json={"offer_id": 3749})
    assert response.status_code == 400
    assert "already" in response.json()["detail"]

    response = client.post("/api/campaigns", json={"name": "x", "geo": "Mexico", "offer_id": 3749})
    assert response.status_code == 400

    assert client.post("/api/campaigns/import", json={"keitaro_id": 1}).status_code == 404
    assert client.get("/api/campaigns/999").status_code == 404


def test_create_campaign(client):
    response = client.post("/api/campaigns", json={"name": "new one", "geo": "mx, au", "offer_id": 11113})
    assert response.status_code == 201
    campaign = response.json()
    flow_1 = campaign["streams"][0]
    assert flow_1["filters"][0]["payload"] == ["MX", "AU"]
    assert shares(campaign)[0] == {11113: 100}


def test_pages_render(client):
    campaign = client.post("/api/campaigns/import", json={"keitaro_id": 93212}).json()
    for url in ("/", "/campaigns/new", f"/campaigns/{campaign['id']}"):
        response = client.get(url)
        assert response.status_code == 200, url
    assert "Fetch streams from KT" in client.get(f"/campaigns/{campaign['id']}").text
