"""Employee model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Employee(Base):
    """Employee model representing a corporate employee who can have trip requests."""

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    tenant_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    employee_ref: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship(back_populates="employees")
    trip_requests: Mapped[list["TripRequest"]] = relationship(back_populates="employee")

    __table_args__ = (
        UniqueConstraint("tenant_id", "employee_ref", name="uq_employee_ref"),
    )


# Import at the end to avoid circular imports
from app.models.tenant import Tenant
from app.models.trip_request import TripRequest
