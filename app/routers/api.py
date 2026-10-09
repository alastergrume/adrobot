"""JSON API used by the web interface (also available at /docs)."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.keitaro import KeitaroClient, get_keitaro
from app.models import Campaign, Stream, StreamOffer
from app.schemas import (
    AddOfferIn,
    CampaignOut,
    ImportCampaignIn,
    KeitaroCampaignOut,
    NewCampaignIn,
    OfferOut,
    PinIn,
)
from app.services import creator, editor

router = APIRouter(prefix="/api", tags=["api"])


def _get(db: Session, model, object_id: int):
    obj = db.get(model, object_id)
    if obj is None:
        raise HTTPException(status_code=404, detail=f"{model.__name__} {object_id} not found")
    return obj


# --- offers and campaigns in Keitaro ------------------------------------------


@router.get("/offers", response_model=list[OfferOut])
def search_offers(
    q: str = Query("", description="Part of the offer name or ID"),
    limit: int = Query(20, ge=1, le=100),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    query = q.strip().lower()
    result = []
    for offer in keitaro.list_offers():
        if offer.get("state", "active") != "active":
            continue
        if query and query not in offer["name"].lower() and query not in str(offer["id"]):
            continue
        result.append(OfferOut(id=offer["id"], name=offer["name"]))
        if len(result) >= limit:
            break
    return result


@router.get("/keitaro/campaigns", response_model=list[KeitaroCampaignOut])
def keitaro_campaigns(db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    local = {c.keitaro_id: c.id for c in db.scalars(select(Campaign))}
    return [
        KeitaroCampaignOut(keitaro_id=c["id"], name=c["name"], local_id=local.get(c["id"]))
        for c in keitaro.list_campaigns()
    ]


# --- campaigns -------------------------------------------------------------------


@router.post("/campaigns", response_model=CampaignOut, status_code=201)
def create_campaign(
    data: NewCampaignIn,
    db: Session = Depends(get_db),
    keitaro: KeitaroClient = Depends(get_keitaro),
):
    new = creator.NewCampaign(name=data.name, geo=creator.parse_geo(data.geo), offer_id=data.offer_id)
    return creator.create_campaign(db, keitaro, new)


@router.post("/campaigns/import", response_model=CampaignOut)
def import_campaign(
    data: ImportCampaignIn, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)
):
    return editor.import_campaign(db, keitaro, data.keitaro_id)


@router.get("/campaigns/{campaign_id}", response_model=CampaignOut)
def get_campaign(campaign_id: int, db: Session = Depends(get_db)):
    return _get(db, Campaign, campaign_id)


@router.post("/campaigns/{campaign_id}/fetch", response_model=CampaignOut)
def fetch_streams(campaign_id: int, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    campaign = _get(db, Campaign, campaign_id)
    editor.sync_campaign(db, keitaro, campaign)
    return campaign


# --- streams and offers ------------------------------------------------------------


@router.post("/streams/{stream_id}/offers", status_code=201)
def add_offer(
    stream_id: int, data: AddOfferIn, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)
):
    offer = editor.add_offer(db, keitaro, _get(db, Stream, stream_id), data.offer_id)
    return {"id": offer.id}


@router.post("/streams/{stream_id}/push")
def push_stream(stream_id: int, db: Session = Depends(get_db), keitaro: KeitaroClient = Depends(get_keitaro)):
    editor.push_stream(db, keitaro, _get(db, Stream, stream_id))
    return {"ok": True}


@router.post("/streams/{stream_id}/cancel")
def cancel_stream(stream_id: int, db: Session = Depends(get_db)):
    editor.cancel_stream(db, _get(db, Stream, stream_id))
    return {"ok": True}


@router.post("/stream-offers/{offer_id}/remove")
def remove_offer(offer_id: int, db: Session = Depends(get_db)):
    editor.remove_offer(db, _get(db, StreamOffer, offer_id))
    return {"ok": True}


@router.post("/stream-offers/{offer_id}/bring-back")
def bring_back(offer_id: int, db: Session = Depends(get_db)):
    editor.bring_back(db, _get(db, StreamOffer, offer_id))
    return {"ok": True}


@router.post("/stream-offers/{offer_id}/pin")
def pin(offer_id: int, data: PinIn, db: Session = Depends(get_db)):
    editor.set_pin(db, _get(db, StreamOffer, offer_id), data.pinned, data.share)
    return {"ok": True}
