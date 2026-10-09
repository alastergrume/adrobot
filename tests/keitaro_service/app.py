"""Fake Keitaro: a test service that answers like the Keitaro Admin API.

The application talks to it through the same HTTP client it uses for the real
tracker, so scenarios can be run on live pages without access to Keitaro.

    uvicorn tests.keitaro_service.app:app --port 8081

API:   /admin_api/v1/...   (requires the Api-Key header, see FAKE_KEITARO_API_KEY)
Admin: /admin/             (look at the data, delete offers "in Keitaro", reset to test data)
"""

from pathlib import Path

from fastapi import APIRouter, Body, Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tests.keitaro_service.settings import service_settings
from tests.keitaro_service.store import KeitaroStore, StoreError

SERVICE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=SERVICE_DIR / "templates")


def describe_filters(filters: list) -> str:
    parts = []
    for item in filters or []:
        payload = item.get("payload")
        values = ", ".join(map(str, payload)) if isinstance(payload, list) else str(payload or "")
        parts.append(f"{item.get('name')} {item.get('mode', '')} {values}".strip())
    return "; ".join(parts)


templates.env.globals["describe_filters"] = describe_filters


def get_store(request: Request) -> KeitaroStore:
    return request.app.state.store


def check_api_key(request: Request, api_key: str | None = Header(default=None, alias="Api-Key")) -> None:
    if api_key != request.app.state.api_key:
        raise HTTPException(status_code=401, detail="Invalid or missing Api-Key header")


# --- Admin API ---------------------------------------------------------------------

api = APIRouter(prefix="/admin_api/v1", dependencies=[Depends(check_api_key)])


@api.get("/campaigns")
def list_campaigns(store: KeitaroStore = Depends(get_store)):
    return store.list_campaigns()


@api.post("/campaigns")
def create_campaign(payload: dict = Body(...), store: KeitaroStore = Depends(get_store)):
    return store.create_campaign(payload)


@api.get("/campaigns/{campaign_id}")
def get_campaign(campaign_id: int, store: KeitaroStore = Depends(get_store)):
    return store.get_campaign(campaign_id)


@api.get("/campaigns/{campaign_id}/streams")
def list_streams(campaign_id: int, store: KeitaroStore = Depends(get_store)):
    return store.list_streams(campaign_id)


@api.post("/streams")
def create_stream(payload: dict = Body(...), store: KeitaroStore = Depends(get_store)):
    return store.create_stream(payload)


@api.put("/streams/{stream_id}")
def update_stream(stream_id: int, payload: dict = Body(...), store: KeitaroStore = Depends(get_store)):
    return store.update_stream(stream_id, payload)


@api.get("/offers")
def list_offers(store: KeitaroStore = Depends(get_store)):
    return store.list_offers()


@api.get("/domains")
def list_domains(store: KeitaroStore = Depends(get_store)):
    return store.list_domains()


@api.get("/groups")
def list_groups(type: str | None = None, store: KeitaroStore = Depends(get_store)):  # noqa: A002 (Keitaro's name)
    return store.list_groups(type)


@api.get("/traffic_sources")
def list_traffic_sources(store: KeitaroStore = Depends(get_store)):
    return store.list_traffic_sources()


# --- Admin pages --------------------------------------------------------------------

admin = APIRouter(include_in_schema=False)


@admin.get("/")
def root():
    return RedirectResponse("/admin/")


@admin.get("/health")
def health():
    return {"ok": True}


@admin.get("/admin/")
def admin_page(request: Request, store: KeitaroStore = Depends(get_store)):
    names = {offer["id"]: offer["name"] for offer in store.list_offers()}
    campaigns = [{"campaign": c, "streams": store.list_streams(c["id"])} for c in store.list_campaigns()]
    return templates.TemplateResponse(request, "admin.html", {"campaigns": campaigns, "offer_names": names})


@admin.post("/admin/streams/{stream_id}/offers/{offer_id}/delete")
def delete_offer(stream_id: int, offer_id: int, store: KeitaroStore = Depends(get_store)):
    stream = store.delete_stream_offer(stream_id, offer_id)
    return RedirectResponse(f"/admin/#!/campaigns/{stream['campaign_id']}", status_code=303)


@admin.post("/admin/reset")
def reset(store: KeitaroStore = Depends(get_store)):
    store.reset()
    return RedirectResponse("/admin/", status_code=303)


# --- application ----------------------------------------------------------------------


def create_app(store: KeitaroStore | None = None, api_key: str | None = None) -> FastAPI:
    service = FastAPI(title="Fake Keitaro Admin API", version="test")
    service.state.store = store or KeitaroStore(service_settings.data_path)
    service.state.api_key = api_key or service_settings.api_key
    service.mount("/static", StaticFiles(directory=SERVICE_DIR / "static"), name="static")
    service.include_router(api)
    service.include_router(admin)

    @service.exception_handler(StoreError)
    def store_error_handler(request: Request, error: StoreError):
        return JSONResponse(status_code=error.status_code, content={"error": str(error)})

    return service


app = create_app()
