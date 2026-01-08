"""Hotel option schemas."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.schemas.common import BaseSchema


class HotelOptionResponse(BaseSchema):
    """Schema for hotel option response."""

    id: UUID
    trip_request_id: UUID
    provider: str
    hotel_id: str
    offer_id: str
    hotel_name: str
    address: str | None
    price_total: Decimal
    price_per_night: Decimal
    currency: str
    rank: int
    created_at: datetime


class HotelOptionBrief(BaseModel):
    """Brief hotel option for display."""

    hotel_id: str
    offer_id: str
    hotel_name: str
    address: str | None
    price_total: Decimal
    price_per_night: Decimal
    currency: str
    rank: int


class TripRequestOptionsResponse(BaseModel):
    """Response with trip request and its options."""

    trip_request_id: UUID
    city: str
    check_in: str
    check_out: str
    options: list[HotelOptionBrief]
