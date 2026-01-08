"""Bulk job models."""

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class BulkJobType(str, Enum):
    """Type enum for bulk jobs."""

    OPTIONS = "OPTIONS"
    BOOK = "BOOK"


class BulkJobStatus(str, Enum):
    """Status enum for bulk jobs."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class BulkJobItemStatus(str, Enum):
    """Status enum for bulk job items."""

    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED_ALREADY_BOOKED = "SKIPPED_ALREADY_BOOKED"
    SKIPPED_NO_OPTIONS = "SKIPPED_NO_OPTIONS"


class BulkJob(Base):
    """Bulk job model for tracking OPTIONS and BOOK jobs."""

    __tablename__ = "bulk_jobs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    job_type: Mapped[BulkJobType] = mapped_column(String(20), nullable=False)
    status: Mapped[BulkJobStatus] = mapped_column(
        String(20), default=BulkJobStatus.PENDING
    )
    total_count: Mapped[int] = mapped_column(default=0)
    success_count: Mapped[int] = mapped_column(default=0)
    failed_count: Mapped[int] = mapped_column(default=0)
    skipped_count: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(nullable=True)

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="bulk_jobs")
    items: Mapped[list["BulkJobItem"]] = relationship(
        back_populates="bulk_job", cascade="all, delete-orphan"
    )


class BulkJobItem(Base):
    """Bulk job item model for tracking individual processing results."""

    __tablename__ = "bulk_job_items"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    bulk_job_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("bulk_jobs.id"), index=True
    )
    trip_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trip_requests.id"), index=True
    )
    employee_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("employees.id"), index=True
    )
    status: Mapped[BulkJobItemStatus] = mapped_column(
        String(30), default=BulkJobItemStatus.PENDING
    )
    error_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("bookings.id"), nullable=True
    )
    options_count: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    bulk_job: Mapped["BulkJob"] = relationship(back_populates="items")
    trip_request: Mapped["TripRequest"] = relationship()
    employee: Mapped["Employee"] = relationship()
    booking: Mapped["Booking"] = relationship()


# Import at the end to avoid circular imports
from app.models.tenant import Tenant
from app.models.trip_request import TripRequest
from app.models.employee import Employee
from app.models.booking import Booking
