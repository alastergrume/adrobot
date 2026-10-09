import pytest

from app.services.shares import SharesError, ShareItem, rebalance, validate_total


def item(key, active=True, pinned=False, share=0, seq=None):
    return ShareItem(key=key, active=active, pinned=pinned, share=share, activation_seq=seq if seq is not None else key)


def test_even_split():
    assert rebalance([item(1), item(2), item(3), item(4)]) == {1: 25, 2: 25, 3: 25, 4: 25}


def test_remainder_goes_to_most_recently_activated():
    assert rebalance([item(1), item(2), item(3)]) == {1: 33, 2: 33, 3: 34}
    assert rebalance([item(1, seq=5), item(2, seq=1), item(3, seq=2)]) == {1: 34, 2: 33, 3: 33}


def test_removed_offers_get_zero():
    shares = rebalance([item(1), item(2, active=False, share=40), item(3)])
    assert shares == {1: 50, 2: 0, 3: 50}


def test_pinned_share_is_kept():
    # The case from the video: one offer pinned at 25%, two others share 75%.
    shares = rebalance([item(1, pinned=True, share=25), item(2, seq=2), item(3, seq=3)])
    assert shares == {1: 25, 2: 37, 3: 38}


def test_removed_pinned_offer_does_not_count():
    shares = rebalance([item(1, active=False, pinned=True, share=60), item(2), item(3)])
    assert shares == {1: 0, 2: 50, 3: 50}


def test_pinned_over_100_is_rejected():
    with pytest.raises(SharesError):
        rebalance([item(1, pinned=True, share=70), item(2, pinned=True, share=40)])


def test_only_pinned_offers_keep_their_shares():
    assert rebalance([item(1, pinned=True, share=30)]) == {1: 30}


def test_shares_always_add_up_to_100():
    for count in range(1, 12):
        for pinned_share in (0, 10, 33, 99):
            items = [item(0, pinned=True, share=pinned_share)] + [item(k) for k in range(1, count + 1)]
            assert sum(rebalance(items).values()) == 100


def test_validate_total():
    validate_total([item(1, share=60), item(2, share=40), item(3, active=False, share=0)])
    with pytest.raises(SharesError):
        validate_total([item(1, share=30)])
    with pytest.raises(SharesError):
        validate_total([item(1, active=False)])
