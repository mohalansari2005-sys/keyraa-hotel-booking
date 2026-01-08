"""Bulk job schemas."""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.bulk_job import BulkJobItemStatus, BulkJobStatus, BulkJobType
from app.schemas.booking import BookingBrief
from app.schemas.common import BaseSchema
from app.schemas.employee import EmployeeBrief
from app.schemas.trip_request import TripRequestBrief


class SelectionStrategy(str, Enum):
    """Strategy for selecting hotel option during bulk booking."""

    CHEAPEST = "CHEAPEST"


class PaymentInfo(BaseModel):
    """Payment information for booking (not stored)."""

    type: str = Field(..., description="Payment type: 'test' or 'card'")
    token: str | None = Field(None, description="Payment token for test mode")
    # Card fields - passed to Amadeus but NOT stored/logged
    card_vendor_code: str | None = Field(None, alias="vendorCode")
    card_number: str | None = Field(None, alias="cardNumber")
    expiry_date: str | None = Field(None, alias="expiryDate")


class OptionsRunRequest(BaseModel):
    """Request to run OPTIONS job."""

    trip_request_ids: list[UUID] | None = Field(
        None, description="Specific trip requests to process (all if empty)"
    )


class BulkBookRequest(BaseModel):
    """Request to run BOOK job."""

    trip_request_ids: list[UUID] | None = Field(
        None, description="Specific trip requests to book (all with options if empty)"
    )
    selection_strategy: SelectionStrategy = SelectionStrategy.CHEAPEST
    email_notifications: bool = True
    payment: PaymentInfo


class BulkJobResponse(BaseSchema):
    """Schema for bulk job status response."""

    id: UUID
    tenant_id: UUID
    job_type: BulkJobType
    status: BulkJobStatus
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    created_at: datetime
    completed_at: datetime | None


class BulkJobItemResult(BaseModel):
    """Result for a single item in a bulk job."""

    item_id: UUID
    status: BulkJobItemStatus
    employee: EmployeeBrief
    trip_request: TripRequestBrief
    error_code: str | None = None
    error_message: str | None = None
    booking: BookingBrief | None = None
    options_count: int | None = None


class BulkJobResultsResponse(BaseModel):
    """Response for bulk job results."""

    job_id: UUID
    job_type: str
    status: str
    total_count: int
    success_count: int
    failed_count: int
    skipped_count: int
    items: list[BulkJobItemResult]
