"""Request and response schemas of the JSON API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OfferOut(BaseModel):
    id: int
    name: str


class StreamOfferOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    offer_name: str
    status: str
    share: int
    pinned: bool
    published_status: str | None
    published_share: int | None
    is_changed: bool


class StreamOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keitaro_id: int
    name: str
    position: int
    schema_: str | None = Field(alias="schema", serialization_alias="schema")
    action_payload: str | None
    filters: list
    has_offers: bool
    is_dirty: bool
    offers: list[StreamOfferOut] = Field(validation_alias="sorted_offers")


class CampaignOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    keitaro_id: int
    name: str
    alias: str | None
    url: str | None
    synced_at: datetime | None
    streams: list[StreamOut]


class KeitaroCampaignOut(BaseModel):
    keitaro_id: int
    name: str
    local_id: int | None


class NewCampaignIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    geo: str = Field(description="Comma-separated two-letter country codes, e.g. MX,AU,RO")
    offer_id: int


class ImportCampaignIn(BaseModel):
    keitaro_id: int


class AddOfferIn(BaseModel):
    offer_id: int


class PinIn(BaseModel):
    pinned: bool = True
    share: int | None = Field(default=None, ge=0, le=100, description="Set the share manually (pins the offer)")
