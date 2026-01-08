"""Booking schemas."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from app.models.booking import BookingStatus
from app.schemas.common import BaseSchema


class BookingResponse(BaseSchema):
    """Schema for booking response."""

    id: UUID
    trip_request_id: UUID
    hotel_option_id: UUID | None
    provider: str
    status: BookingStatus
    amadeus_order_id: str | None
    amadeus_reference: str | None
    hotel_name: str
    hotel_address: str | None
    check_in: date
    check_out: date
    total_price: Decimal
    currency: str
    error_code: str | None
    error_message: str | None
    email_sent: bool
    created_at: datetime


class BookingBrief(BaseModel):
    """Brief booking info for job results."""

    booking_id: UUID
    status: str
    hotel_name: str
    amadeus_reference: str | None
    total_price: Decimal
    currency: str
