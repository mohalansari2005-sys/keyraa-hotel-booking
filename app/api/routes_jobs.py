"""Job status and results routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, TenantId
from app.models.booking import Booking
from app.models.bulk_job import BulkJob, BulkJobItem
from app.models.employee import Employee
from app.models.trip_request import TripRequest
from app.schemas.booking import BookingBrief
from app.schemas.bulk_job import (
    BulkJobItemResult,
    BulkJobResponse,
    BulkJobResultsResponse,
)
from app.schemas.employee import EmployeeBrief
from app.schemas.trip_request import TripRequestBrief

router = APIRouter(prefix="/v1/bulk/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=BulkJobResponse)
async def get_job_status(
    db: DBSession,
    tenant_id: TenantId,
    job_id: UUID,
) -> BulkJobResponse:
    """Get the status and progress of a bulk job."""
    result = await db.execute(
        select(BulkJob).where(
            BulkJob.id == job_id,
            BulkJob.tenant_id == tenant_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return BulkJobResponse.model_validate(job)


@router.get("/{job_id}/results", response_model=BulkJobResultsResponse)
async def get_job_results(
    db: DBSession,
    tenant_id: TenantId,
    job_id: UUID,
) -> BulkJobResultsResponse:
    """Get detailed results for each item in a bulk job."""
    # Get job
    result = await db.execute(
        select(BulkJob).where(
            BulkJob.id == job_id,
            BulkJob.tenant_id == tenant_id,
        )
    )
    job = result.scalar_one_or_none()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Get job items with related data
    result = await db.execute(
        select(BulkJobItem)
        .options(
            joinedload(BulkJobItem.employee),
            joinedload(BulkJobItem.trip_request),
            joinedload(BulkJobItem.booking),
        )
        .where(BulkJobItem.bulk_job_id == job_id)
    )
    items = result.unique().scalars().all()

    # Build response
    item_results = []
    for item in items:
        # Build employee brief
        employee_brief = EmployeeBrief(
            id=item.employee.id,
            employee_ref=item.employee.employee_ref,
            name=item.employee.name,
            email=item.employee.email,
        )

        # Build trip request brief
        trip_brief = TripRequestBrief(
            id=item.trip_request.id,
            city=item.trip_request.city,
            check_in=item.trip_request.check_in,
            check_out=item.trip_request.check_out,
            max_nightly_budget=item.trip_request.max_nightly_budget,
            status=item.trip_request.status.value if hasattr(item.trip_request.status, 'value') else str(item.trip_request.status),
        )

        # Build booking brief if exists
        booking_brief = None
        if item.booking:
            booking_brief = BookingBrief(
                booking_id=item.booking.id,
                status=item.booking.status.value if hasattr(item.booking.status, 'value') else str(item.booking.status),
                hotel_name=item.booking.hotel_name,
                amadeus_reference=item.booking.amadeus_reference,
                total_price=item.booking.total_price,
                currency=item.booking.currency,
            )

        item_results.append(
            BulkJobItemResult(
                item_id=item.id,
                status=item.status,
                employee=employee_brief,
                trip_request=trip_brief,
                error_code=item.error_code,
                error_message=item.error_message,
                booking=booking_brief,
                options_count=item.options_count,
            )
        )

    return BulkJobResultsResponse(
        job_id=job.id,
        job_type=job.job_type.value if hasattr(job.job_type, 'value') else str(job.job_type),
        status=job.status.value if hasattr(job.status, 'value') else str(job.status),
        total_count=job.total_count,
        success_count=job.success_count,
        failed_count=job.failed_count,
        skipped_count=job.skipped_count,
        items=item_results,
    )
