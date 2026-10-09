"""Campaign creator: a campaign with two streams.

Flow 1 catches visitors from the given countries and redirects them to
Google; Flow 2 sends everyone else to the selected offer.
"""

import re
import secrets
import string
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.configs import campaign_settings
from app.keitaro import KeitaroClient
from app.models import Campaign
from app.services.editor import EditorError, import_campaign

COUNTRY_RE = re.compile(r"^[A-Z]{2}$")
ALIAS_CHARS = string.ascii_letters + string.digits


@dataclass
class NewCampaign:
    name: str
    geo: list[str]
    offer_id: int


def parse_geo(raw: str) -> list[str]:
    """'mx, AU ,ro' -> ['MX', 'AU', 'RO'] (two-letter ISO codes, duplicates removed)."""
    codes: list[str] = []
    for part in re.split(r"[\s,;]+", raw.strip()):
        if not part:
            continue
        code = part.upper()
        if not COUNTRY_RE.match(code):
            raise EditorError(f"'{part}' is not a two-letter country code")
        if code not in codes:
            codes.append(code)
    if not codes:
        raise EditorError("Specify at least one country")
    return codes


def _normalize_domain(name: str) -> str:
    return re.sub(r"^https?://", "", name.strip().lower()).rstrip("/")


def _find_id(items: list[dict], name: str, normalize=lambda value: value.strip().lower()) -> int | None:
    wanted = normalize(name)
    for item in items:
        if normalize(item.get("name", "")) == wanted:
            return item["id"]
    return None


def create_campaign(db: Session, keitaro: KeitaroClient, data: NewCampaign) -> Campaign:
    name = data.name.strip()
    if not name:
        raise EditorError("Campaign name is required")
    if not any(offer["id"] == data.offer_id for offer in keitaro.list_offers()):
        raise EditorError(f"Offer {data.offer_id} not found in Keitaro")

    payload = {
        "alias": "".join(secrets.choice(ALIAS_CHARS) for _ in range(8)),
        "name": name,
        "type": "position",
        "state": "active",
        "domain_id": _find_id(keitaro.list_domains(), campaign_settings.domain, _normalize_domain),
        "group_id": _find_id(keitaro.list_campaign_groups(), campaign_settings.group),
        "traffic_source_id": _find_id(keitaro.list_traffic_sources(), campaign_settings.source),
    }
    remote = keitaro.create_campaign({key: value for key, value in payload.items() if value is not None})

    keitaro.create_stream(
        {
            "campaign_id": remote["id"],
            "type": "regular",
            "name": "Flow 1",
            "position": 1,
            "state": "active",
            "schema": "redirect",
            "action_type": "http",
            "action_payload": campaign_settings.geo_redirect_url,
            "filters": [{"name": "country", "mode": "accept", "payload": data.geo}],
        }
    )
    keitaro.create_stream(
        {
            "campaign_id": remote["id"],
            "type": "regular",
            "name": "Flow 2",
            "position": 2,
            "state": "active",
            "schema": "landings",
            "action_type": "http",
            "offers": [{"offer_id": data.offer_id, "share": 100, "state": "active"}],
        }
    )
    return import_campaign(db, keitaro, remote["id"])
