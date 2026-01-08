"""Tenant model."""

import uuid
from datetime import datetime

from sqlalchemy import String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Tenant(Base):
    """Tenant model for multi-tenancy support."""

    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    # Relationships
    employees: Mapped[list["Employee"]] = relationship(back_populates="tenant")
    trip_requests: Mapped[list["TripRequest"]] = relationship(back_populates="tenant")
    bulk_jobs: Mapped[list["BulkJob"]] = relationship(back_populates="tenant")


# Import at the end to avoid circular imports
from app.models.employee import Employee
from app.models.trip_request import TripRequest
from app.models.bulk_job import BulkJob
