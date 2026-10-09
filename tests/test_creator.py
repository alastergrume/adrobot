import pytest

from app.services.creator import NewCampaign, create_campaign, parse_geo
from app.services.editor import EditorError


def test_parse_geo():
    assert parse_geo("MX,AU,RO") == ["MX", "AU", "RO"]
    assert parse_geo(" mx, au ;ro mx ") == ["MX", "AU", "RO"]
    with pytest.raises(EditorError):
        parse_geo("Mexico")
    with pytest.raises(EditorError):
        parse_geo(" , ")


def test_create_campaign_with_two_streams(db, keitaro):
    campaign = create_campaign(db, keitaro, NewCampaign(name="test campaign", geo=["MX", "AU"], offer_id=11112))

    remote = keitaro.get_campaign(campaign.keitaro_id)
    assert remote["name"] == "test campaign"
    assert (remote["domain_id"], remote["group_id"], remote["traffic_source_id"]) == (1, 1, 1)

    flow_1, flow_2 = keitaro.list_streams(campaign.keitaro_id)
    assert flow_1["schema"] == "redirect" and flow_1["action_payload"] == "https://google.com"
    assert flow_1["filters"] == [{"name": "country", "mode": "accept", "payload": ["MX", "AU"]}]
    assert flow_2["schema"] == "landings"
    assert [(o["offer_id"], o["share"]) for o in flow_2["offers"]] == [(11112, 100)]

    # The new campaign is ready for the editor.
    assert campaign.url == f"https://in.posdk.xyz/{remote['alias']}"
    assert [s.name for s in campaign.streams] == ["Flow 1", "Flow 2"]
    assert [(o.offer_id, o.share) for o in campaign.streams[1].offers] == [(11112, 100)]


def test_create_campaign_with_unknown_offer(db, keitaro):
    with pytest.raises(EditorError):
        create_campaign(db, keitaro, NewCampaign(name="x", geo=["MX"], offer_id=1))
    assert len(keitaro.list_campaigns()) == 1  # nothing was created
