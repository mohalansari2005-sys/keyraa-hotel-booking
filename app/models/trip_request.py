"""Trip request model."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    Date,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class TripRequestStatus(str, Enum):
    """Status enum for trip requests."""

    PENDING = "PENDING"
    OPTIONS_READY = "OPTIONS_READY"
    BOOKED = "BOOKED"
    FAILED = "FAILED"


class TripRequest(Base):
    """Trip request model representing an employee's hotel booking requirement."""

    __tablename__ = "trip_requests"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id"), index=True
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    check_in: Mapped[date] = mapped_column(Date, nullable=False)
    check_out: Mapped[date] = mapped_column(Date, nullable=False)
    max_nightly_budget: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[TripRequestStatus] = mapped_column(
        String(20), default=TripRequestStatus.PENDING
    )
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="trip_requests")
    employee: Mapped["Employee"] = relationship(back_populates="trip_requests")
    hotel_options: Mapped[list["HotelOption"]] = relationship(
        back_populates="trip_request", cascade="all, delete-orphan"
    )
    booking: Mapped["Booking"] = relationship(
        back_populates="trip_request", uselist=False
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "employee_id",
            "check_in",
            "check_out",
            "city",
            name="uq_trip_request",
        ),
        Index("ix_trip_request_status", "status"),
    )


# Import at the end to avoid circular imports
from app.models.tenant import Tenant
from app.models.employee import Employee
from app.models.hotel_option import HotelOption
from app.models.booking import Booking
