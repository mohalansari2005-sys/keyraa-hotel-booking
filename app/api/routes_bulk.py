"""Bulk operation routes for employees, trip requests, and bookings."""

import csv
import io
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.api.deps import DBSession, TenantId, ensure_tenant_exists
from app.core.logging import get_logger
from app.models.bulk_job import BulkJob, BulkJobItem, BulkJobStatus, BulkJobType
from app.models.employee import Employee
from app.models.trip_request import TripRequest, TripRequestStatus
from app.schemas.bulk_job import BulkBookRequest, OptionsRunRequest
from app.schemas.common import BulkSummary, JobResponse
from app.schemas.employee import EmployeeBulkCreate, EmployeeCreate
from app.schemas.trip_request import TripRequestBulkCreate, TripRequestCreate
from app.workers.tasks import book_bulk_job, generate_options_job

logger = get_logger(__name__)

router = APIRouter(prefix="/v1/bulk", tags=["bulk"])


# ============================================================================
# Employee Bulk Upload
# ============================================================================


@router.post("/employees", response_model=BulkSummary)
async def bulk_upload_employees(
    db: DBSession,
    tenant_id: TenantId,
    employees: EmployeeBulkCreate = Body(...),
) -> BulkSummary:
    """
    Bulk create or update employees via JSON.
    
    Idempotent by (tenant_id, employee_ref).
    """
    await ensure_tenant_exists(db, tenant_id)
    return await _process_employees(db, tenant_id, employees.employees)


@router.post("/employees/csv", response_model=BulkSummary)
async def bulk_upload_employees_csv(
    db: DBSession,
    tenant_id: TenantId,
    file: UploadFile = File(...),
) -> BulkSummary:
    """
    Bulk create or update employees via CSV upload.
    
    CSV columns: employee_ref, name, email
    """
    await ensure_tenant_exists(db, tenant_id)
    employee_list = await _parse_employee_csv(file)
    return await _process_employees(db, tenant_id, employee_list)


async def _process_employees(
    db: DBSession,
    tenant_id: UUID,
    employee_list: list[EmployeeCreate],
) -> BulkSummary:
    """Process a list of employees."""
    summary = BulkSummary()

    for emp_data in employee_list:
        try:
            # Check if exists
            result = await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.employee_ref == emp_data.employee_ref,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update
                existing.name = emp_data.name
                existing.email = emp_data.email
                summary.updated += 1
            else:
                # Create
                employee = Employee(
                    tenant_id=tenant_id,
                    employee_ref=emp_data.employee_ref,
                    name=emp_data.name,
                    email=emp_data.email,
                )
                db.add(employee)
                summary.created += 1

        except Exception as e:
            logger.error(f"Error processing employee {emp_data.employee_ref}: {e}")
            summary.errors.append({
                "employee_ref": emp_data.employee_ref,
                "error": str(e),
            })

    await db.commit()
    return summary


async def _parse_employee_csv(file: UploadFile) -> list[EmployeeCreate]:
    """Parse CSV file to employee list."""
    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    employees = []
    for row in reader:
        try:
            emp = EmployeeCreate(
                employee_ref=row.get("employee_ref", "").strip(),
                name=row.get("name", "").strip(),
                email=row.get("email", "").strip(),
            )
            employees.append(emp)
        except ValidationError as e:
            logger.warning(f"Invalid row in CSV: {row}, error: {e}")

    return employees


# ============================================================================
# Trip Request Bulk Upload
# ============================================================================


@router.post("/trip-requests", response_model=BulkSummary)
async def bulk_upload_trip_requests(
    db: DBSession,
    tenant_id: TenantId,
    trip_requests: TripRequestBulkCreate = Body(...),
) -> BulkSummary:
    """
    Bulk create trip requests via JSON.
    
    Idempotent by (tenant_id, employee_id, check_in, check_out, city).
    """
    await ensure_tenant_exists(db, tenant_id)
    return await _process_trip_requests(db, tenant_id, trip_requests.trip_requests)


@router.post("/trip-requests/csv", response_model=BulkSummary)
async def bulk_upload_trip_requests_csv(
    db: DBSession,
    tenant_id: TenantId,
    file: UploadFile = File(...),
) -> BulkSummary:
    """
    Bulk create trip requests via CSV upload.
    
    CSV columns: employee_ref, city, check_in, check_out, max_nightly_budget
    """
    await ensure_tenant_exists(db, tenant_id)
    request_list = await _parse_trip_request_csv(file)
    return await _process_trip_requests(db, tenant_id, request_list)


async def _process_trip_requests(
    db: DBSession,
    tenant_id: UUID,
    request_list: list[TripRequestCreate],
) -> BulkSummary:
    """Process a list of trip requests."""
    summary = BulkSummary()

    for req_data in request_list:
        try:
            # Find employee
            result = await db.execute(
                select(Employee).where(
                    Employee.tenant_id == tenant_id,
                    Employee.employee_ref == req_data.employee_ref,
                )
            )
            employee = result.scalar_one_or_none()

            if not employee:
                summary.errors.append({
                    "employee_ref": req_data.employee_ref,
                    "error": f"Employee not found: {req_data.employee_ref}",
                })
                continue

            # Check for duplicate
            result = await db.execute(
                select(TripRequest).where(
                    TripRequest.tenant_id == tenant_id,
                    TripRequest.employee_id == employee.id,
                    TripRequest.city == req_data.city,
                    TripRequest.check_in == req_data.check_in,
                    TripRequest.check_out == req_data.check_out,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                summary.skipped += 1
                continue

            # Create trip request
            trip_request = TripRequest(
                tenant_id=tenant_id,
                employee_id=employee.id,
                city=req_data.city,
                check_in=req_data.check_in,
                check_out=req_data.check_out,
                max_nightly_budget=req_data.max_nightly_budget,
                status=TripRequestStatus.PENDING,
            )
            db.add(trip_request)
            summary.created += 1

        except Exception as e:
            logger.error(f"Error processing trip request: {e}")
            summary.errors.append({
                "employee_ref": req_data.employee_ref,
                "error": str(e),
            })

    await db.commit()
    return summary


async def _parse_trip_request_csv(file: UploadFile) -> list[TripRequestCreate]:
    """Parse CSV file to trip request list."""
    from datetime import date
    from decimal import Decimal

    content = await file.read()
    text = content.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    requests = []
    for row in reader:
        try:
            req = TripRequestCreate(
                employee_ref=row.get("employee_ref", "").strip(),
                city=row.get("city", "").strip(),
                check_in=date.fromisoformat(row.get("check_in", "").strip()),
                check_out=date.fromisoformat(row.get("check_out", "").strip()),
                max_nightly_budget=Decimal(row.get("max_nightly_budget", "0").strip()),
            )
            requests.append(req)
        except (ValidationError, ValueError) as e:
            logger.warning(f"Invalid row in CSV: {row}, error: {e}")

    return requests


# ============================================================================
# Options Generation
# ============================================================================


@router.post("/options/run", response_model=JobResponse)
async def run_options_job(
    db: DBSession,
    tenant_id: TenantId,
    request: OptionsRunRequest = Body(default=OptionsRunRequest()),
) -> JobResponse:
    """
    Start a job to generate hotel options for trip requests.
    
    If trip_request_ids is empty, processes all PENDING trip requests.
    """
    await ensure_tenant_exists(db, tenant_id)

    # Get trip requests to process
    query = select(TripRequest).where(
        TripRequest.tenant_id == tenant_id,
    )

    if request.trip_request_ids:
        query = query.where(TripRequest.id.in_(request.trip_request_ids))
    else:
        query = query.where(TripRequest.status == TripRequestStatus.PENDING)

    result = await db.execute(query)
    trip_requests = result.scalars().all()

    if not trip_requests:
        raise HTTPException(
            status_code=404,
            detail="No trip requests found to process",
        )

    # Create bulk job
    job = BulkJob(
        tenant_id=tenant_id,
        job_type=BulkJobType.OPTIONS,
        status=BulkJobStatus.PENDING,
        total_count=len(trip_requests),
    )
    db.add(job)
    await db.flush()

    # Create job items
    for tr in trip_requests:
        item = BulkJobItem(
            bulk_job_id=job.id,
            trip_request_id=tr.id,
            employee_id=tr.employee_id,
        )
        db.add(item)

    await db.commit()

    # Queue the job
    generate_options_job.delay(str(job.id))

    logger.info(f"Queued OPTIONS job {job.id} with {len(trip_requests)} items")

    return JobResponse(
        job_id=job.id,
        status="PENDING",
        message=f"Options job queued for {len(trip_requests)} trip requests",
    )


# ============================================================================
# Bulk Booking
# ============================================================================


@router.post("/book", response_model=JobResponse)
async def run_book_job(
    db: DBSession,
    tenant_id: TenantId,
    request: BulkBookRequest = Body(...),
) -> JobResponse:
    """
    Start a job to book hotels for trip requests.
    
    If trip_request_ids is empty, books all trip requests with OPTIONS_READY status.
    """
    await ensure_tenant_exists(db, tenant_id)

    # Get trip requests to process
    query = select(TripRequest).where(
        TripRequest.tenant_id == tenant_id,
    )

    if request.trip_request_ids:
        query = query.where(TripRequest.id.in_(request.trip_request_ids))
    else:
        query = query.where(TripRequest.status == TripRequestStatus.OPTIONS_READY)

    result = await db.execute(query)
    trip_requests = result.scalars().all()

    if not trip_requests:
        raise HTTPException(
            status_code=404,
            detail="No trip requests found to book",
        )

    # Create bulk job
    job = BulkJob(
        tenant_id=tenant_id,
        job_type=BulkJobType.BOOK,
        status=BulkJobStatus.PENDING,
        total_count=len(trip_requests),
    )
    db.add(job)
    await db.flush()

    # Create job items
    for tr in trip_requests:
        item = BulkJobItem(
            bulk_job_id=job.id,
            trip_request_id=tr.id,
            employee_id=tr.employee_id,
        )
        db.add(item)

    await db.commit()

    # Prepare payment info (convert Pydantic to dict, exclude None values)
    payment_dict = request.payment.model_dump(exclude_none=True)

    # Queue the job (payment info passed but never stored)
    book_bulk_job.delay(str(job.id), payment_dict)

    logger.info(f"Queued BOOK job {job.id} with {len(trip_requests)} items")

    return JobResponse(
        job_id=job.id,
        status="PENDING",
        message=f"Booking job queued for {len(trip_requests)} trip requests",
    )
