"""Hotel option model."""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import ForeignKey, JSON, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class HotelOption(Base):
    """Hotel option model storing Amadeus hotel offers for a trip request."""

    __tablename__ = "hotel_options"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trip_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trip_requests.id"), index=True
    )
    provider: Mapped[str] = mapped_column(String(50), default="amadeus")
    hotel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    offer_id: Mapped[str] = mapped_column(String(255), nullable=False)
    hotel_name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_total: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    rank: Mapped[int] = mapped_column(nullable=False)  # 1 = cheapest
    payload_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    trip_request: Mapped["TripRequest"] = relationship(back_populates="hotel_options")


# Import at the end to avoid circular imports
from app.models.trip_request import TripRequest
