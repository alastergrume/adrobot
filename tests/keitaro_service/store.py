"""Data storage of the fake Keitaro service.

Objects are plain dicts in the same shape as the Keitaro Admin API returns them.
With a path the data lives in a JSON file (re-read on every call, so
seed_test_data.py can reset it while the service is running); without a path
it is kept in memory, which is what the unit tests use.
"""

import copy
import json
import random
import string
import threading
from pathlib import Path

from tests.keitaro_service.seed_test_data import test_data, write_test_data


class StoreError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


class KeitaroStore:
    def __init__(self, path: str | Path | None = None):
        self._path = Path(path) if path else None
        self._lock = threading.RLock()
        self._data = test_data()

    # --- storage -----------------------------------------------------------

    def _load(self) -> None:
        if self._path:
            if not self._path.exists():
                write_test_data(self._path)  # first start: fill with the test data
            self._data = json.loads(self._path.read_text(encoding="utf-8"))

    def _save(self) -> None:
        if self._path:
            self._path.write_text(json.dumps(self._data, ensure_ascii=False, indent=2), encoding="utf-8")

    def _read(self, collection: str) -> list[dict]:
        with self._lock:
            self._load()
            return copy.deepcopy(self._data[collection])

    def _next_id(self, kind: str) -> int:
        value = self._data["next_ids"][kind]
        self._data["next_ids"][kind] = value + 1
        return value

    def _find(self, collection: str, object_id: int) -> dict:
        for item in self._data[collection]:
            if item["id"] == object_id:
                return item
        raise StoreError(f"{collection[:-1].replace('_', ' ')} {object_id} not found", status_code=404)

    def _normalize_offers(self, stream_id: int, offers: list[dict], previous: list[dict]) -> list[dict]:
        known = {offer["id"] for offer in self._data["offers"]}
        link_ids = {link["offer_id"]: link["id"] for link in previous}
        result = []
        for item in offers:
            offer_id = int(item["offer_id"])
            if offer_id not in known:
                raise StoreError(f"offer {offer_id} not found", status_code=422)
            share = int(item.get("share", 100))
            if not 0 <= share <= 100:
                raise StoreError(f"share must be between 0 and 100, got {share}", status_code=422)
            result.append(
                {
                    "id": link_ids.get(offer_id) or self._next_id("stream_offer"),
                    "stream_id": stream_id,
                    "offer_id": offer_id,
                    "state": item.get("state", "active"),
                    "share": share,
                }
            )
        return result

    # --- read ----------------------------------------------------------------

    def list_campaigns(self) -> list[dict]:
        return self._read("campaigns")

    def get_campaign(self, campaign_id: int) -> dict:
        with self._lock:
            self._load()
            return copy.deepcopy(self._find("campaigns", campaign_id))

    def list_streams(self, campaign_id: int) -> list[dict]:
        with self._lock:
            self._load()
            self._find("campaigns", campaign_id)
            streams = [s for s in self._data["streams"] if s["campaign_id"] == campaign_id]
            return copy.deepcopy(sorted(streams, key=lambda s: s["position"]))

    def get_stream(self, stream_id: int) -> dict:
        with self._lock:
            self._load()
            return copy.deepcopy(self._find("streams", stream_id))

    def list_offers(self) -> list[dict]:
        return self._read("offers")

    def list_domains(self) -> list[dict]:
        return self._read("domains")

    def list_groups(self, group_type: str | None = None) -> list[dict]:
        groups = self._read("groups")
        return [g for g in groups if group_type is None or g.get("type") == group_type]

    def list_traffic_sources(self) -> list[dict]:
        return self._read("traffic_sources")

    # --- write ---------------------------------------------------------------

    def create_campaign(self, payload: dict) -> dict:
        if not payload.get("name"):
            raise StoreError("campaign name is required", status_code=422)
        with self._lock:
            self._load()
            campaign = {
                "id": self._next_id("campaign"),
                "alias": payload.get("alias") or "".join(random.choices(string.ascii_letters + string.digits, k=6)),
                "name": payload["name"],
                "type": payload.get("type", "position"),
                "state": payload.get("state", "active"),
                "domain_id": payload.get("domain_id"),
                "group_id": payload.get("group_id"),
                "traffic_source_id": payload.get("traffic_source_id"),
            }
            self._data["campaigns"].append(campaign)
            self._save()
            return copy.deepcopy(campaign)

    def create_stream(self, payload: dict) -> dict:
        with self._lock:
            self._load()
            campaign_id = int(payload.get("campaign_id") or 0)
            self._find("campaigns", campaign_id)
            positions = [s["position"] for s in self._data["streams"] if s["campaign_id"] == campaign_id]
            stream_id = self._next_id("stream")
            stream = {
                "id": stream_id,
                "campaign_id": campaign_id,
                "type": payload.get("type", "regular"),
                "name": payload.get("name") or f"Stream {stream_id}",
                "position": payload.get("position") or max(positions, default=0) + 1,
                "state": payload.get("state", "active"),
                "schema": payload.get("schema", "landings"),
                "action_type": payload.get("action_type", "http"),
                "action_payload": payload.get("action_payload"),
                "filters": copy.deepcopy(payload.get("filters", [])),
                "offers": self._normalize_offers(stream_id, payload.get("offers", []), []),
            }
            self._data["streams"].append(stream)
            self._save()
            return copy.deepcopy(stream)

    def update_stream(self, stream_id: int, payload: dict) -> dict:
        with self._lock:
            self._load()
            stream = self._find("streams", stream_id)
            for key in ("name", "position", "state", "schema", "action_type", "action_payload", "filters"):
                if key in payload:
                    stream[key] = copy.deepcopy(payload[key])
            if "offers" in payload:
                stream["offers"] = self._normalize_offers(stream_id, payload["offers"], stream["offers"])
            self._save()
            return copy.deepcopy(stream)

    def delete_stream_offer(self, stream_id: int, offer_id: int) -> dict:
        """What a user does in the Keitaro admin: the other offers keep their shares."""
        with self._lock:
            self._load()
            stream = self._find("streams", stream_id)
            stream["offers"] = [link for link in stream["offers"] if link["offer_id"] != offer_id]
            self._save()
            return copy.deepcopy(stream)

    def reset(self) -> None:
        with self._lock:
            self._data = test_data()
            if self._path:
                write_test_data(self._path)
