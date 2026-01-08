"""Celery tasks for bulk job processing."""

import asyncio
from datetime import datetime
from typing import Any
from uuid import UUID

from celery import shared_task
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.core.db import get_sync_session
from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.bulk_job import (
    BulkJob,
    BulkJobItem,
    BulkJobItemStatus,
    BulkJobStatus,
    BulkJobType,
)
from app.models.employee import Employee
from app.models.hotel_option import HotelOption
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.amadeus_client import AmadeusClient, AmadeusError, MockAmadeusClient
from app.services.email_service import get_email_service
from app.workers.celery_app import celery_app

logger = get_logger(__name__)

# Use mock client for testing (configurable via environment)
import os
USE_MOCK_CLIENT = os.environ.get("USE_MOCK_AMADEUS", "true").lower() == "true"


def get_amadeus_client():
    """Get Amadeus client (real or mock based on configuration)."""
    if USE_MOCK_CLIENT:
        return MockAmadeusClient()
    return AmadeusClient()


def run_async(coro):
    """Helper to run async code in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                return loop.run_until_complete(coro)
            finally:
                loop.close()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(coro)


@celery_app.task(bind=True, max_retries=3)
def generate_options_job(self, job_id: str) -> dict[str, Any]:
    """
    Generate hotel options for all trip requests in a bulk job.
    """
    logger.info(f"Starting OPTIONS job {job_id}")
    db = get_sync_session()

    try:
        # Get the job
        job = db.query(BulkJob).filter(BulkJob.id == UUID(job_id)).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"error": "Job not found"}

        # Update job status
        job.status = BulkJobStatus.PROCESSING
        db.commit()

        # Get all job items with their trip requests
        items = (
            db.query(BulkJobItem)
            .options(
                joinedload(BulkJobItem.trip_request),
                joinedload(BulkJobItem.employee),
            )
            .filter(BulkJobItem.bulk_job_id == job.id)
            .all()
        )

        amadeus_client = get_amadeus_client()
        success_count = 0
        failed_count = 0

        for item in items:
            try:
                item.status = BulkJobItemStatus.PROCESSING
                db.commit()

                # Fetch options
                options_count = run_async(
                    _fetch_and_store_options(
                        db=db,
                        trip_request=item.trip_request,
                        amadeus_client=amadeus_client,
                    )
                )

                if options_count > 0:
                    item.status = BulkJobItemStatus.SUCCESS
                    item.options_count = options_count
                    success_count += 1
                else:
                    item.status = BulkJobItemStatus.FAILED
                    item.error_code = "NO_OPTIONS"
                    item.error_message = "No hotel options found matching criteria"
                    failed_count += 1

            except AmadeusError as e:
                logger.error(f"Amadeus error for item {item.id}: {e}")
                item.status = BulkJobItemStatus.FAILED
                item.error_code = str(e.status_code) if e.status_code else "AMADEUS_ERROR"
                item.error_message = str(e)
                failed_count += 1

            except Exception as e:
                logger.exception(f"Unexpected error for item {item.id}")
                item.status = BulkJobItemStatus.FAILED
                item.error_code = "INTERNAL_ERROR"
                item.error_message = str(e)
                failed_count += 1

            db.commit()

        # Update job completion status
        job.success_count = success_count
        job.failed_count = failed_count
        job.status = BulkJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(f"OPTIONS job {job_id} completed: {success_count} success, {failed_count} failed")

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "success_count": success_count,
            "failed_count": failed_count,
        }

    except Exception as e:
        logger.exception(f"Fatal error in OPTIONS job {job_id}")
        db.rollback()

        try:
            job = db.query(BulkJob).filter(BulkJob.id == UUID(job_id)).first()
            if job:
                job.status = BulkJobStatus.FAILED
                db.commit()
        except Exception:
            pass

        raise self.retry(exc=e)

    finally:
        db.close()


async def _fetch_and_store_options(
    db,
    trip_request: TripRequest,
    amadeus_client,
    max_options: int = 5,
) -> int:
    """Fetch hotel options from Amadeus and store the top options."""
    from app.services.option_service import parse_and_rank_offers
    
    logger.info(
        f"Fetching options for trip request {trip_request.id}: "
        f"{trip_request.city} {trip_request.check_in} to {trip_request.check_out}"
    )

    # Delete existing options
    existing = db.query(HotelOption).filter(
        HotelOption.trip_request_id == trip_request.id
    ).all()
    for option in existing:
        db.delete(option)

    # Fetch offers from Amadeus
    offers = await amadeus_client.get_hotel_offers(
        city_code=trip_request.city,
        check_in=trip_request.check_in,
        check_out=trip_request.check_out,
        max_price=trip_request.max_nightly_budget,
    )

    if not offers:
        logger.warning(f"No offers found for trip request {trip_request.id}")
        trip_request.status = TripRequestStatus.FAILED
        db.commit()
        return 0

    # Parse and rank offers
    parsed_offers = parse_and_rank_offers(
        offers,
        trip_request.check_in,
        trip_request.check_out,
        trip_request.max_nightly_budget,
    )

    # Store top options
    stored_count = 0
    for rank, offer in enumerate(parsed_offers[:max_options], start=1):
        option = HotelOption(
            trip_request_id=trip_request.id,
            provider="amadeus",
            hotel_id=offer["hotel_id"],
            offer_id=offer["offer_id"],
            hotel_name=offer["hotel_name"],
            address=offer.get("address"),
            price_total=offer["price_total"],
            price_per_night=offer["price_per_night"],
            currency=offer["currency"],
            rank=rank,
            payload_json=offer.get("raw_offer"),
        )
        db.add(option)
        stored_count += 1

    # Update trip request status
    trip_request.status = TripRequestStatus.OPTIONS_READY
    db.commit()

    logger.info(f"Stored {stored_count} options for trip request {trip_request.id}")
    return stored_count


@celery_app.task(bind=True, max_retries=3)
def book_bulk_job(self, job_id: str, payment_info: dict[str, Any]) -> dict[str, Any]:
    """Book hotels for all trip requests in a bulk job."""
    logger.info(f"Starting BOOK job {job_id}")
    db = get_sync_session()
    email_service = get_email_service()

    try:
        job = db.query(BulkJob).filter(BulkJob.id == UUID(job_id)).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return {"error": "Job not found"}

        job.status = BulkJobStatus.PROCESSING
        db.commit()

        items = (
            db.query(BulkJobItem)
            .options(
                joinedload(BulkJobItem.trip_request).joinedload(TripRequest.hotel_options),
                joinedload(BulkJobItem.employee),
            )
            .filter(BulkJobItem.bulk_job_id == job.id)
            .all()
        )

        amadeus_client = get_amadeus_client()
        success_count = 0
        failed_count = 0
        skipped_count = 0

        for item in items:
            try:
                # Check if already booked
                existing_booking = db.query(Booking).filter(
                    Booking.trip_request_id == item.trip_request_id,
                    Booking.status == BookingStatus.CONFIRMED,
                ).first()

                if existing_booking:
                    item.status = BulkJobItemStatus.SKIPPED_ALREADY_BOOKED
                    item.booking_id = existing_booking.id
                    skipped_count += 1
                    db.commit()
                    continue

                # Check if options exist
                if not item.trip_request.hotel_options:
                    item.status = BulkJobItemStatus.SKIPPED_NO_OPTIONS
                    item.error_code = "NO_OPTIONS"
                    item.error_message = "No hotel options available"
                    failed_count += 1
                    db.commit()
                    continue

                item.status = BulkJobItemStatus.PROCESSING
                db.commit()

                # Book the hotel
                booking = run_async(
                    _book_trip_request(
                        db=db,
                        trip_request=item.trip_request,
                        employee=item.employee,
                        amadeus_client=amadeus_client,
                        payment_info=payment_info,
                    )
                )

                if booking.status == BookingStatus.CONFIRMED:
                    item.status = BulkJobItemStatus.SUCCESS
                    item.booking_id = booking.id
                    success_count += 1

                    # Send confirmation email
                    try:
                        email_sent = email_service.send_booking_confirmation(
                            employee=item.employee,
                            booking=booking,
                        )
                        booking.email_sent = email_sent
                    except Exception as e:
                        logger.error(f"Email error for booking {booking.id}: {e}")
                        booking.email_sent = False

                else:
                    item.status = BulkJobItemStatus.FAILED
                    item.error_code = booking.error_code
                    item.error_message = booking.error_message
                    item.booking_id = booking.id
                    failed_count += 1

                    try:
                        email_service.send_booking_failure(
                            employee=item.employee,
                            trip_request=item.trip_request,
                            reason=booking.error_message or "Unknown error",
                        )
                    except Exception as e:
                        logger.error(f"Failed to send failure email: {e}")

            except AmadeusError as e:
                logger.error(f"Amadeus error for item {item.id}: {e}")
                item.status = BulkJobItemStatus.FAILED
                item.error_code = str(e.status_code) if e.status_code else "AMADEUS_ERROR"
                item.error_message = str(e)
                failed_count += 1

            except Exception as e:
                logger.exception(f"Unexpected error for item {item.id}")
                item.status = BulkJobItemStatus.FAILED
                item.error_code = "INTERNAL_ERROR"
                item.error_message = str(e)
                failed_count += 1

            db.commit()

        job.success_count = success_count
        job.failed_count = failed_count
        job.skipped_count = skipped_count
        job.status = BulkJobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"BOOK job {job_id} completed: "
            f"{success_count} success, {failed_count} failed, {skipped_count} skipped"
        )

        return {
            "job_id": job_id,
            "status": "COMPLETED",
            "success_count": success_count,
            "failed_count": failed_count,
            "skipped_count": skipped_count,
        }

    except Exception as e:
        logger.exception(f"Fatal error in BOOK job {job_id}")
        db.rollback()

        try:
            job = db.query(BulkJob).filter(BulkJob.id == UUID(job_id)).first()
            if job:
                job.status = BulkJobStatus.FAILED
                db.commit()
        except Exception:
            pass

        raise self.retry(exc=e)

    finally:
        db.close()


async def _book_trip_request(
    db,
    trip_request: TripRequest,
    employee: Employee,
    amadeus_client,
    payment_info: dict[str, Any],
) -> Booking:
    """Book a hotel for a trip request."""
    from decimal import Decimal
    from app.services.booking_service import select_option, build_payment_payload, sanitize_response
    
    logger.info(f"Booking trip request {trip_request.id} for employee {employee.employee_ref}")

    # Get the best option
    option = select_option(db, trip_request.id, "CHEAPEST")

    if not option:
        booking = Booking(
            trip_request_id=trip_request.id,
            hotel_option_id=None,
            provider="amadeus",
            status=BookingStatus.FAILED,
            hotel_name="N/A",
            check_in=trip_request.check_in,
            check_out=trip_request.check_out,
            total_price=Decimal("0"),
            currency="USD",
            error_code="NO_OPTIONS",
            error_message="No hotel options available for this trip request",
        )
        db.add(booking)
        trip_request.status = TripRequestStatus.FAILED
        db.commit()
        return booking

    # Prepare guest information
    name_parts = employee.name.split(" ", 1)
    guests = [
        {
            "id": 1,
            "name": {
                "title": "MR",
                "firstName": name_parts[0],
                "lastName": name_parts[1] if len(name_parts) > 1 else name_parts[0],
            },
            "contact": {
                "phone": "+1234567890",
                "email": employee.email,
            },
        }
    ]

    payments = build_payment_payload(payment_info)

    booking = Booking(
        trip_request_id=trip_request.id,
        hotel_option_id=option.id,
        provider="amadeus",
        status=BookingStatus.PENDING,
        hotel_name=option.hotel_name,
        hotel_address=option.address,
        check_in=trip_request.check_in,
        check_out=trip_request.check_out,
        total_price=option.price_total,
        currency=option.currency,
    )
    db.add(booking)
    db.flush()

    try:
        response = await amadeus_client.create_hotel_order(
            offer_id=option.offer_id,
            guests=guests,
            payments=payments,
        )

        order_data = response.get("data", {})
        booking.amadeus_order_id = order_data.get("id")
        booking.amadeus_reference = order_data.get("reference")
        booking.status = BookingStatus.CONFIRMED
        booking.raw_response_json = sanitize_response(response)

        trip_request.status = TripRequestStatus.BOOKED

        logger.info(f"Booking confirmed: {booking.amadeus_reference}")

    except AmadeusError as e:
        logger.error(f"Booking failed: {e}")
        booking.status = BookingStatus.FAILED
        booking.error_code = str(e.status_code) if e.status_code else "UNKNOWN"
        booking.error_message = str(e)
        trip_request.status = TripRequestStatus.FAILED

    db.commit()
    return booking
