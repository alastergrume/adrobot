"""Test data for the fake Keitaro service.

It mirrors the campaign from the task video: "campaign 2" with a geo redirect
flow and an offers flow, plus several offers to search and add.

Usage (writes the data file of the service):
    python -m tests.keitaro_service.seed_test_data            # reset to the test data
    python -m tests.keitaro_service.seed_test_data --if-empty # only if there is no data yet
"""

import argparse
import copy
import json
from pathlib import Path

TEST_DATA: dict = {
    "domains": [{"id": 1, "name": "in.posdk.xyz"}],
    "groups": [{"id": 1, "name": "FORTESTS", "type": "campaigns"}],
    "traffic_sources": [{"id": 1, "name": "FORTESTS"}],
    "offers": [
        {"id": 3717, "name": "Miaflow [BEAUTY-RO-BE_0008] [pl -- prize ro -] 1. Основной, Румыния JS", "state": "active"},
        {"id": 3749, "name": "Miaflow [BEAUTY-RO-BE_0009] [pl -- spin ro -] 2. Основной, Румыния JS", "state": "active"},
        {"id": 11111, "name": "11111 FitoMishki [Weight Loss-CO-DT_0309] [pl es -]", "state": "active"},
        {"id": 11112, "name": "11112 Oxys [BEAUTY-CL-BE_0155] [pl es -]", "state": "active"},
        {"id": 11113, "name": "11113 Cardiol [HEALTH-MX-CA_0101] [pl es -]", "state": "active"},
        {"id": 11114, "name": "11114 Keto Light [Weight Loss-AU-DT_0211] [pl en -]", "state": "active"},
        {"id": 11115, "name": "11115 Hondrocream [JOINTS-PL-JN_0042] [pl pl -]", "state": "active"},
        {"id": 11116, "name": "11116 Gluconol [DIABETES-MX-DB_0077] [pl es -]", "state": "active"},
    ],
    "campaigns": [
        {
            "id": 93212,
            "alias": "wVqN1R",
            "name": "campaign 2",
            "type": "position",
            "state": "active",
            "domain_id": 1,
            "group_id": 1,
            "traffic_source_id": 1,
        }
    ],
    "streams": [
        {
            "id": 564220,
            "campaign_id": 93212,
            "type": "regular",
            "name": "Flow 1",
            "position": 1,
            "state": "active",
            "schema": "redirect",
            "action_type": "http",
            "action_payload": "https://google.com",
            "filters": [{"name": "country", "mode": "accept", "payload": ["AU"]}],
            "offers": [],
        },
        {
            "id": 564221,
            "campaign_id": 93212,
            "type": "regular",
            "name": "Flow 2",
            "position": 2,
            "state": "active",
            "schema": "landings",
            "action_type": "http",
            "action_payload": None,
            "filters": [],
            "offers": [
                {"id": 1, "stream_id": 564221, "offer_id": 3749, "state": "active", "share": 33},
                {"id": 2, "stream_id": 564221, "offer_id": 3717, "state": "active", "share": 33},
                {"id": 3, "stream_id": 564221, "offer_id": 11111, "state": "active", "share": 34},
            ],
        },
    ],
    "next_ids": {"campaign": 93213, "stream": 564222, "stream_offer": 4},
}


def test_data() -> dict:
    """A fresh copy of the test data."""
    return copy.deepcopy(TEST_DATA)


test_data.__test__ = False  # not a pytest test


def write_test_data(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(test_data(), ensure_ascii=False, indent=2), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    from tests.keitaro_service.settings import service_settings

    parser = argparse.ArgumentParser(description="Fill the fake Keitaro service with test data.")
    parser.add_argument("--path", type=Path, default=Path(service_settings.data_path), help="data file of the service")
    parser.add_argument("--if-empty", action="store_true", help="keep existing data")
    args = parser.parse_args(argv)

    if args.if_empty and args.path.exists():
        print(f"Fake Keitaro data already exists: {args.path}")
        return 0
    write_test_data(args.path)
    data = TEST_DATA
    print(
        f"Fake Keitaro test data written to {args.path}: "
        f"{len(data['campaigns'])} campaign(s), {len(data['streams'])} streams, {len(data['offers'])} offers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
