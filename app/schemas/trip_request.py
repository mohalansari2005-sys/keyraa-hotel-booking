"""Trip request schemas."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.trip_request import TripRequestStatus
from app.schemas.common import BaseSchema


class TripRequestCreate(BaseModel):
    """Schema for creating a trip request."""

    employee_ref: str = Field(..., min_length=1, max_length=100)
    city: str = Field(..., min_length=2, max_length=100, description="IATA city code (e.g., PAR, LON)")
    check_in: date
    check_out: date
    max_nightly_budget: Decimal = Field(..., gt=0, decimal_places=2)

    @model_validator(mode="after")
    def validate_dates(self) -> "TripRequestCreate":
        """Ensure check_in is before check_out."""
        if self.check_in >= self.check_out:
            raise ValueError("check_in must be before check_out")
        return self

    @field_validator("city")
    @classmethod
    def uppercase_city(cls, v: str) -> str:
        """Convert city code to uppercase."""
        return v.upper()


class TripRequestBulkCreate(BaseModel):
    """Schema for bulk trip request upload (list)."""

    trip_requests: list[TripRequestCreate]


class TripRequestResponse(BaseSchema):
    """Schema for trip request response."""

    id: UUID
    tenant_id: UUID
    employee_id: UUID
    city: str
    check_in: date
    check_out: date
    max_nightly_budget: Decimal
    status: TripRequestStatus
    created_at: datetime


class TripRequestBrief(BaseSchema):
    """Brief trip request info for job results."""

    id: UUID
    city: str
    check_in: date
    check_out: date
    max_nightly_budget: Decimal
    status: str
