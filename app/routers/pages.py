"""Server-rendered pages. Buttons on the pages call the JSON API."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.configs import campaign_settings, keitaro_settings
from app.configs.env import APP_ENV
from app.db import get_db
from app.keitaro import KeitaroClient, KeitaroError, get_keitaro
from app.models import Campaign

router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=Path(__file__).resolve().parent.parent / "templates")


def describe_filters(filters: list) -> str:
    parts = []
    for item in filters or []:
        payload = item.get("payload")
        values = ", ".join(map(str, payload)) if isinstance(payload, list) else str(payload or "")
        parts.append(f"{item.get('name')} {item.get('mode', '')} {values}".strip())
    return "; ".join(parts)


templates.env.globals.update(
    describe_filters=describe_filters,
    keitaro_settings=keitaro_settings,
    campaign_settings=campaign_settings,
    app_env=APP_ENV,
)


@router.get("/")
def campaigns_page(
    request: Request,
    db: Session = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    local = list(db.scalars(select(Campaign).order_by(Campaign.created_at.desc())))
    imported = {c.keitaro_id for c in local}
    error = None
    try:
        remote = [c for c in keitaro.list_campaigns() if c["id"] not in imported]
    except KeitaroError as exc:
        remote, error = [], str(exc)
    return templates.TemplateResponse(
        request,
        "campaigns.html",
        {"campaigns": local, "remote_campaigns": remote, "keitaro_error": error},
    )


@router.get("/campaigns/new")
def new_campaign_page(request: Request):
    return templates.TemplateResponse(request, "new_campaign.html")


@router.get("/campaigns/{campaign_id}")
def editor_page(campaign_id: int, request: Request, db: Session = Depends(get_db)):
    campaign = db.get(Campaign, campaign_id)
    if campaign is None:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return templates.TemplateResponse(
        request,
        "editor.html",
        {"campaign": campaign, "keitaro_link": keitaro_settings.campaign_link(campaign.keitaro_id)},
    )
