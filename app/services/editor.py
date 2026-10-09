"""Campaign editor: synchronization with Keitaro and offer operations.

Changes made in the interface stay local (the stream turns "dirty") until
the user pushes the stream to Keitaro or cancels the changes.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.keitaro import KeitaroClient
from app.models import ACTIVE, REMOVED, Campaign, Stream, StreamOffer, utcnow
from app.services.shares import SharesError, ShareItem, rebalance, validate_total


class EditorError(ValueError):
    pass


# --- helpers ---------------------------------------------------------------


def _share_items(stream: Stream) -> list[ShareItem]:
    return [
        ShareItem(
            key=offer.id,
            active=offer.is_active,
            pinned=offer.pinned,
            share=offer.share,
            activation_seq=offer.activation_seq,
        )
        for offer in stream.offers
    ]


def _rebalance(stream: Stream) -> None:
    try:
        shares = rebalance(_share_items(stream))
    except SharesError as error:
        raise EditorError(str(error)) from error
    for offer in stream.offers:
        offer.share = shares[offer.id]


def _next_seq(stream: Stream) -> int:
    return max((offer.activation_seq for offer in stream.offers), default=0) + 1


def _require_offer_stream(stream: Stream) -> None:
    if not stream.has_offers:
        raise EditorError(f"Stream '{stream.name}' does not send traffic to offers and cannot be edited here")


def _domain_name(keitaro: KeitaroClient, domain_id: int | None) -> str | None:
    if not domain_id:
        return None
    for domain in keitaro.list_domains():
        if domain["id"] == domain_id:
            return domain["name"]
    return None


# --- campaigns ---------------------------------------------------------------


def import_campaign(db: Session, keitaro: KeitaroClient, keitaro_campaign_id: int) -> Campaign:
    """Start editing a Keitaro campaign: create a local record and fetch its streams."""
    campaign = db.scalar(select(Campaign).where(Campaign.keitaro_id == keitaro_campaign_id))
    if campaign is None:
        data = keitaro.get_campaign(keitaro_campaign_id)
        campaign = Campaign(
            keitaro_id=data["id"],
            name=data["name"],
            alias=data.get("alias"),
            domain=_domain_name(keitaro, data.get("domain_id")),
        )
        db.add(campaign)
        db.flush()
    sync_campaign(db, keitaro, campaign)
    return campaign


def sync_campaign(db: Session, keitaro: KeitaroClient, campaign: Campaign) -> None:
    """Fetch streams from Keitaro. Keitaro is the source of truth: unpublished
    changes are discarded, offers that disappeared from Keitaro are archived."""
    remote_streams = keitaro.list_streams(campaign.keitaro_id)
    offer_names = {offer["id"]: offer["name"] for offer in keitaro.list_offers()}

    local_streams = {stream.keitaro_id: stream for stream in campaign.streams}
    seen = set()
    for remote in remote_streams:
        seen.add(remote["id"])
        stream = local_streams.get(remote["id"])
        if stream is None:
            stream = Stream(keitaro_id=remote["id"], campaign=campaign, name=remote.get("name") or "")
            db.add(stream)
        stream.name = remote.get("name") or f"Stream {remote['id']}"
        stream.position = remote.get("position") or 0
        stream.schema = remote.get("schema")
        stream.state = remote.get("state")
        stream.action_payload = remote.get("action_payload")
        stream.filters = remote.get("filters") or []
        _sync_stream_offers(db, stream, remote.get("offers") or [], offer_names)

    for keitaro_id, stream in local_streams.items():
        if keitaro_id not in seen:
            campaign.streams.remove(stream)

    campaign.synced_at = utcnow()
    db.commit()


def _sync_stream_offers(db: Session, stream: Stream, remote_offers: list[dict], offer_names: dict) -> None:
    # Drop links that were added locally but never published.
    for offer in [o for o in stream.offers if o.is_new]:
        stream.offers.remove(offer)

    remote_active = {}
    for link in sorted(remote_offers, key=lambda link: link.get("id") or 0):
        if link.get("state", ACTIVE) == ACTIVE:
            remote_active[int(link["offer_id"])] = int(link.get("share", 0))

    local = {offer.offer_id: offer for offer in stream.offers}
    seq = _next_seq(stream)
    for offer_id, share in remote_active.items():
        offer = local.get(offer_id)
        if offer is None:
            offer = StreamOffer(offer_id=offer_id, activation_seq=seq)
            seq += 1
            stream.offers.append(offer)
        elif offer.status != ACTIVE:
            offer.activation_seq = seq
            seq += 1
        offer.status = offer.published_status = ACTIVE
        offer.share = offer.published_share = share
        offer.offer_name = offer_names.get(offer_id, offer.offer_name or f"Offer {offer_id}")

    for offer_id, offer in local.items():
        if offer_id not in remote_active:
            offer.status = offer.published_status = REMOVED
            offer.share = offer.published_share = 0
            offer.offer_name = offer_names.get(offer_id, offer.offer_name)
    db.flush()


# --- offer operations ----------------------------------------------------------


def add_offer(db: Session, keitaro: KeitaroClient, stream: Stream, offer_id: int) -> StreamOffer:
    _require_offer_stream(stream)
    existing = next((o for o in stream.offers if o.offer_id == offer_id), None)
    if existing is not None:
        if existing.is_active:
            raise EditorError(f"Offer {offer_id} is already in the stream")
        return bring_back(db, existing)

    name = next((o["name"] for o in keitaro.list_offers() if o["id"] == offer_id), None)
    if name is None:
        raise EditorError(f"Offer {offer_id} not found in Keitaro")

    offer = StreamOffer(offer_id=offer_id, offer_name=name, status=ACTIVE, share=0, activation_seq=_next_seq(stream))
    stream.offers.append(offer)
    db.flush()
    _rebalance(stream)
    db.commit()
    return offer


def remove_offer(db: Session, offer: StreamOffer) -> None:
    stream = offer.stream
    if offer.is_new:
        # Never published: removing simply undoes the addition.
        stream.offers.remove(offer)
    else:
        offer.status = REMOVED
        offer.pinned = False
    db.flush()
    _rebalance(stream)
    db.commit()


def bring_back(db: Session, offer: StreamOffer) -> StreamOffer:
    if offer.is_active:
        raise EditorError("Offer is already active")
    stream = offer.stream
    offer.status = ACTIVE
    offer.activation_seq = _next_seq(stream)
    _rebalance(stream)
    db.commit()
    return offer


def set_pin(db: Session, offer: StreamOffer, pinned: bool, share: int | None = None) -> StreamOffer:
    """Pin or unpin an offer. Passing a share sets it manually (and pins it)."""
    if not offer.is_active:
        raise EditorError("Only active offers can be pinned")
    stream = offer.stream
    if share is None:
        offer.pinned = pinned
        db.commit()
        return offer

    if not 0 <= share <= 100:
        raise EditorError("Share must be between 0 and 100")
    others_pinned = sum(o.share for o in stream.offers if o.is_active and o.pinned and o.id != offer.id)
    if others_pinned + share > 100:
        raise EditorError(f"Pinned shares would add up to {others_pinned + share}%, more than 100%")
    offer.share = share
    offer.pinned = True
    _rebalance(stream)
    db.commit()
    return offer


# --- publishing -----------------------------------------------------------------


def push_stream(db: Session, keitaro: KeitaroClient, stream: Stream) -> None:
    _require_offer_stream(stream)
    try:
        validate_total(_share_items(stream))
    except SharesError as error:
        raise EditorError(str(error)) from error

    active = sorted((o for o in stream.offers if o.is_active), key=lambda o: o.activation_seq)
    payload = [{"offer_id": o.offer_id, "share": o.share, "state": ACTIVE} for o in active]
    keitaro.update_stream(stream.keitaro_id, {"offers": payload})

    for offer in list(stream.offers):
        if offer.is_new and not offer.is_active:
            stream.offers.remove(offer)
            continue
        offer.published_status = offer.status
        offer.published_share = offer.share
    db.commit()


def cancel_stream(db: Session, stream: Stream) -> None:
    for offer in list(stream.offers):
        if offer.is_new:
            stream.offers.remove(offer)
            continue
        offer.status = offer.published_status
        offer.share = offer.published_share
    db.commit()
