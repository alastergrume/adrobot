"""Editor scenarios, following the reference video step by step."""

import pytest

from app.models import ACTIVE, REMOVED
from app.services import editor
from app.services.editor import EditorError

CAMPAIGN = 93212
FLOW_2 = 564221
MIAFLOW_9, MIAFLOW_8, FITOMISHKI, OXYS, CARDIOL = 3749, 3717, 11111, 11112, 11113


def offers_stream(campaign):
    return next(s for s in campaign.streams if s.keitaro_id == FLOW_2)


def local_shares(stream):
    return {o.offer_id: (o.status, o.share) for o in stream.offers}


def remote_shares(keitaro):
    stream = next(s for s in keitaro.list_streams(CAMPAIGN) if s["id"] == FLOW_2)
    return {link["offer_id"]: link["share"] for link in stream["offers"]}


def find(stream, offer_id):
    return next(o for o in stream.offers if o.offer_id == offer_id)


@pytest.fixture
def campaign(db, keitaro):
    return editor.import_campaign(db, keitaro, CAMPAIGN)


def test_fetch_streams(campaign):
    flow_1, flow_2 = campaign.streams
    assert flow_1.name == "Flow 1" and not flow_1.has_offers and flow_1.offers == []
    assert flow_1.filters == [{"name": "country", "mode": "accept", "payload": ["AU"]}]
    assert local_shares(flow_2) == {MIAFLOW_9: (ACTIVE, 33), MIAFLOW_8: (ACTIVE, 33), FITOMISHKI: (ACTIVE, 34)}
    assert not flow_2.is_dirty


def test_add_offer_recalculates_and_waits_for_push(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)

    assert {k: v[1] for k, v in local_shares(stream).items()} == {MIAFLOW_9: 25, MIAFLOW_8: 25, FITOMISHKI: 25, OXYS: 25}
    assert stream.is_dirty
    assert remote_shares(keitaro) == {MIAFLOW_9: 33, MIAFLOW_8: 33, FITOMISHKI: 34}  # Keitaro untouched

    editor.push_stream(db, keitaro, stream)
    assert remote_shares(keitaro) == {MIAFLOW_9: 25, MIAFLOW_8: 25, FITOMISHKI: 25, OXYS: 25}
    assert not stream.is_dirty


def test_cancel_drops_unpublished_offer(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.cancel_stream(db, stream)

    assert local_shares(stream) == {MIAFLOW_9: (ACTIVE, 33), MIAFLOW_8: (ACTIVE, 33), FITOMISHKI: (ACTIVE, 34)}
    assert not stream.is_dirty


def test_remove_archives_offer_and_bring_back_returns_it(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.push_stream(db, keitaro, stream)

    editor.remove_offer(db, find(stream, MIAFLOW_8))
    assert local_shares(stream) == {
        OXYS: (ACTIVE, 34),  # most recently added gets the remainder
        MIAFLOW_9: (ACTIVE, 33),
        FITOMISHKI: (ACTIVE, 33),
        MIAFLOW_8: (REMOVED, 0),
    }
    assert stream.is_dirty

    editor.push_stream(db, keitaro, stream)
    assert MIAFLOW_8 not in remote_shares(keitaro)
    assert find(stream, MIAFLOW_8).status == REMOVED  # still in our archive
    assert not stream.is_dirty

    editor.bring_back(db, find(stream, MIAFLOW_8))
    assert stream.is_dirty
    editor.push_stream(db, keitaro, stream)
    assert remote_shares(keitaro) == {MIAFLOW_9: 25, MIAFLOW_8: 25, FITOMISHKI: 25, OXYS: 25}


def test_cancel_restores_removed_offer(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.remove_offer(db, find(stream, MIAFLOW_9))
    editor.cancel_stream(db, stream)
    assert local_shares(stream) == {MIAFLOW_9: (ACTIVE, 33), MIAFLOW_8: (ACTIVE, 33), FITOMISHKI: (ACTIVE, 34)}
    assert not stream.is_dirty


def test_offers_deleted_in_keitaro_become_removed(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.push_stream(db, keitaro, stream)

    # Someone deletes two offers directly in Keitaro.
    keitaro.update_stream(FLOW_2, {"offers": [{"offer_id": MIAFLOW_8, "share": 25}, {"offer_id": OXYS, "share": 25}]})
    editor.sync_campaign(db, keitaro, campaign)

    stream = offers_stream(campaign)
    assert local_shares(stream) == {
        MIAFLOW_8: (ACTIVE, 25),
        OXYS: (ACTIVE, 25),
        MIAFLOW_9: (REMOVED, 0),
        FITOMISHKI: (REMOVED, 0),
    }
    assert not stream.is_dirty


def test_pinned_share_survives_recalculation(db, keitaro, campaign):
    """Video, 4:30-5:20: pin 25%, bring back an offer -> 38/37/25."""
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.push_stream(db, keitaro, stream)
    keitaro.update_stream(FLOW_2, {"offers": [{"offer_id": MIAFLOW_8, "share": 25}, {"offer_id": OXYS, "share": 25}]})
    editor.sync_campaign(db, keitaro, campaign)

    editor.set_pin(db, find(stream, MIAFLOW_8), pinned=True)
    editor.bring_back(db, find(stream, MIAFLOW_9))

    assert {k: v for k, v in local_shares(stream).items() if v[0] == ACTIVE} == {
        MIAFLOW_9: (ACTIVE, 38),
        OXYS: (ACTIVE, 37),
        MIAFLOW_8: (ACTIVE, 25),
    }
    editor.push_stream(db, keitaro, stream)
    assert remote_shares(keitaro) == {MIAFLOW_9: 38, OXYS: 37, MIAFLOW_8: 25}


def test_manual_share_pins_offer(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.set_pin(db, find(stream, MIAFLOW_9), pinned=True, share=50)
    assert find(stream, MIAFLOW_9).pinned
    assert local_shares(stream) == {MIAFLOW_9: (ACTIVE, 50), MIAFLOW_8: (ACTIVE, 25), FITOMISHKI: (ACTIVE, 25)}

    editor.add_offer(db, keitaro, stream, OXYS)
    assert find(stream, MIAFLOW_9).share == 50
    assert sum(o.share for o in stream.offers) == 100


def test_pinned_shares_cannot_exceed_100(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.set_pin(db, find(stream, MIAFLOW_9), pinned=True, share=70)
    with pytest.raises(EditorError):
        editor.set_pin(db, find(stream, MIAFLOW_8), pinned=True, share=40)


def test_push_rejects_shares_not_adding_up(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.set_pin(db, find(stream, MIAFLOW_9), pinned=True, share=40)
    editor.remove_offer(db, find(stream, MIAFLOW_8))
    editor.remove_offer(db, find(stream, FITOMISHKI))
    with pytest.raises(EditorError):
        editor.push_stream(db, keitaro, stream)
    assert remote_shares(keitaro) == {MIAFLOW_9: 33, MIAFLOW_8: 33, FITOMISHKI: 34}


def test_removing_unpublished_offer_deletes_it(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.remove_offer(db, find(stream, OXYS))
    assert OXYS not in local_shares(stream)
    assert not stream.is_dirty


def test_add_existing_offer(db, keitaro, campaign):
    stream = offers_stream(campaign)
    with pytest.raises(EditorError):
        editor.add_offer(db, keitaro, stream, MIAFLOW_9)

    editor.remove_offer(db, find(stream, MIAFLOW_9))
    editor.add_offer(db, keitaro, stream, MIAFLOW_9)  # acts as "bring back"
    assert find(stream, MIAFLOW_9).status == ACTIVE


def test_add_unknown_offer(db, keitaro, campaign):
    with pytest.raises(EditorError):
        editor.add_offer(db, keitaro, offers_stream(campaign), 999999)


def test_sync_discards_unpublished_changes(db, keitaro, campaign):
    stream = offers_stream(campaign)
    editor.add_offer(db, keitaro, stream, OXYS)
    editor.remove_offer(db, find(stream, MIAFLOW_9))
    editor.sync_campaign(db, keitaro, campaign)
    assert local_shares(stream) == {MIAFLOW_9: (ACTIVE, 33), MIAFLOW_8: (ACTIVE, 33), FITOMISHKI: (ACTIVE, 34)}


def test_redirect_stream_is_read_only(db, keitaro, campaign):
    flow_1 = campaign.streams[0]
    with pytest.raises(EditorError):
        editor.add_offer(db, keitaro, flow_1, OXYS)
