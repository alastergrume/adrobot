"""Distribution of traffic shares between the offers of a stream.

Shares are whole percents and active offers always add up to 100:
  * removed offers get 0;
  * pinned offers keep their share;
  * the rest of 100% is split evenly between unpinned active offers;
  * if it does not split evenly, the remainder goes one percent at a time
    to the most recently activated offers (as in the reference tool:
    34/33/33, 38/37).
"""

from dataclasses import dataclass

TOTAL = 100


class SharesError(ValueError):
    pass


@dataclass(frozen=True)
class ShareItem:
    key: int
    active: bool
    pinned: bool
    share: int
    activation_seq: int


def rebalance(items: list[ShareItem]) -> dict[int, int]:
    """Return the new share for every item key."""
    result = {item.key: 0 for item in items if not item.active}

    pinned = [item for item in items if item.active and item.pinned]
    free = [item for item in items if item.active and not item.pinned]

    pinned_total = sum(item.share for item in pinned)
    if pinned_total > TOTAL:
        raise SharesError(f"Pinned shares add up to {pinned_total}%, more than {TOTAL}%")
    for item in pinned:
        result[item.key] = item.share

    if free:
        base, remainder = divmod(TOTAL - pinned_total, len(free))
        most_recent_first = sorted(free, key=lambda item: (-item.activation_seq, -item.key))
        for index, item in enumerate(most_recent_first):
            result[item.key] = base + (1 if index < remainder else 0)

    return result


def validate_total(items: list[ShareItem]) -> None:
    """Check that a stream can be published."""
    active = [item for item in items if item.active]
    if not active:
        raise SharesError("A stream must have at least one active offer")
    total = sum(item.share for item in active)
    if total != TOTAL:
        raise SharesError(f"Active offers add up to {total}%, expected {TOTAL}%. Unpin or change a pinned share")
