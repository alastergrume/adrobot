"""Database models.

Every offer in a stream has two states:
  * the draft (``status``, ``share``) that the user edits in the interface;
  * the published one (``published_status``, ``published_share``) that is
    currently in Keitaro. ``published_status`` is None for offers that were
    added in the interface and have never been pushed.

A stream is "dirty" (shown in yellow) when the draft differs from the
published state. Removed offers stay in the database as an archive so they
can be brought back.
"""

from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base

ACTIVE = "active"
REMOVED = "removed"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[int] = mapped_column(primary_key=True)
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    alias: Mapped[str | None] = mapped_column(String(64))
    domain: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    streams: Mapped[list["Stream"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan", order_by="Stream.position"
    )

    @property
    def url(self) -> str | None:
        if not self.domain or not self.alias:
            return None
        domain = self.domain if "://" in self.domain else f"https://{self.domain}"
        return f"{domain.rstrip('/')}/{self.alias}"


class Stream(Base):
    __tablename__ = "streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("campaigns.id", ondelete="CASCADE"), index=True)
    keitaro_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    position: Mapped[int] = mapped_column(Integer, default=0)
    schema: Mapped[str | None] = mapped_column(String(32))
    state: Mapped[str | None] = mapped_column(String(32))
    action_payload: Mapped[str | None] = mapped_column(String(2048))
    filters: Mapped[list] = mapped_column(JSON, default=list)

    campaign: Mapped[Campaign] = relationship(back_populates="streams")
    offers: Mapped[list["StreamOffer"]] = relationship(
        back_populates="stream", cascade="all, delete-orphan", order_by="StreamOffer.id"
    )

    @property
    def has_offers(self) -> bool:
        """Offer streams can be edited; redirect streams are shown as is."""
        return self.schema == "landings" or bool(self.offers)

    @property
    def is_dirty(self) -> bool:
        return any(offer.is_changed for offer in self.offers)

    @property
    def sorted_offers(self) -> list["StreamOffer"]:
        """Active offers by share (largest first), removed ones at the bottom."""
        return sorted(self.offers, key=lambda o: (o.status != ACTIVE, -o.share, o.id or 0))


class StreamOffer(Base):
    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "offer_id", name="uq_stream_offer"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("streams.id", ondelete="CASCADE"), index=True)
    offer_id: Mapped[int] = mapped_column(Integer)
    offer_name: Mapped[str] = mapped_column(String(512), default="")

    status: Mapped[str] = mapped_column(String(16), default=ACTIVE)
    share: Mapped[int] = mapped_column(Integer, default=0)
    published_status: Mapped[str | None] = mapped_column(String(16))
    published_share: Mapped[int | None] = mapped_column(Integer)

    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    # Order in which offers became active; the most recently activated
    # offers receive the remainder when 100% does not split evenly.
    activation_seq: Mapped[int] = mapped_column(Integer, default=0)

    stream: Mapped[Stream] = relationship(back_populates="offers")

    @property
    def is_active(self) -> bool:
        return self.status == ACTIVE

    @property
    def is_new(self) -> bool:
        return self.published_status is None

    @property
    def is_changed(self) -> bool:
        if self.is_new:
            return True
        return (self.status, self.share) != (self.published_status, self.published_share)
