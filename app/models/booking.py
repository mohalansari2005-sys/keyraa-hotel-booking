"""Booking model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import Date, ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BookingStatus(str, Enum):
    """Status enum for bookings."""

    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


class Booking(Base):
    """Booking model storing confirmed hotel reservations."""

    __tablename__ = "bookings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trip_requests.id"), index=True
    )
    hotel_option_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("hotel_options.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="amadeus")
    status: Mapped[BookingStatus] = mapped_column(
        String(20), default=BookingStatus.PENDING
    )
    amadeus_order_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amadeus_reference: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hotel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    hotel_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    raw_response_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_sent: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    trip_request: Mapped["TripRequest"] = relationship(back_populates="booking")
    hotel_option: Mapped["HotelOption"] = relationship()


# Import at the end to avoid circular imports
from app.models.trip_request import TripRequest
from app.models.hotel_option import HotelOption
