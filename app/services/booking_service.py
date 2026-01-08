"""Booking service for processing hotel bookings."""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.booking import Booking, BookingStatus
from app.models.employee import Employee
from app.models.hotel_option import HotelOption
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.amadeus_client import AmadeusError, BaseAmadeusClient

logger = get_logger(__name__)


async def book_trip_request(
    db: Session,
    trip_request: TripRequest,
    employee: Employee,
    amadeus_client: BaseAmadeusClient,
    payment_info: dict[str, Any],
    selection_strategy: str = "CHEAPEST",
) -> Booking:
    """
    Book a hotel for a trip request.

    Args:
        db: Database session
        trip_request: The trip request to book
        employee: The employee for the booking
        amadeus_client: Amadeus API client
        payment_info: Payment information (NOT stored)
        selection_strategy: Strategy for selecting option (currently only CHEAPEST)

    Returns:
        Booking record
    """
    logger.info(f"Booking trip request {trip_request.id} for employee {employee.employee_ref}")

    # Check if already booked
    existing_booking = db.query(Booking).filter(
        Booking.trip_request_id == trip_request.id,
        Booking.status == BookingStatus.CONFIRMED,
    ).first()

    if existing_booking:
        logger.info(f"Trip request {trip_request.id} already has confirmed booking")
        return existing_booking

    # Get the best option based on strategy
    option = select_option(db, trip_request.id, selection_strategy)

    if not option:
        logger.warning(f"No options available for trip request {trip_request.id}")
        # Create a failed booking record
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
                "title": "MR",  # Default, could be made configurable
                "firstName": name_parts[0],
                "lastName": name_parts[1] if len(name_parts) > 1 else name_parts[0],
            },
            "contact": {
                "phone": "+1234567890",  # Placeholder
                "email": employee.email,
            },
        }
    ]

    # Prepare payment information (not logged/stored)
    payments = build_payment_payload(payment_info)

    # Create booking record (pending)
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
        # Call Amadeus booking API
        response = await amadeus_client.create_hotel_order(
            offer_id=option.offer_id,
            guests=guests,
            payments=payments,
        )

        # Extract confirmation details
        order_data = response.get("data", {})
        booking.amadeus_order_id = order_data.get("id")
        booking.amadeus_reference = order_data.get("reference")
        booking.status = BookingStatus.CONFIRMED
        booking.raw_response_json = sanitize_response(response)

        trip_request.status = TripRequestStatus.BOOKED

        logger.info(
            f"Booking confirmed: {booking.amadeus_reference} for trip {trip_request.id}"
        )

    except AmadeusError as e:
        logger.error(f"Booking failed for trip {trip_request.id}: {e}")
        booking.status = BookingStatus.FAILED
        booking.error_code = str(e.status_code) if e.status_code else "UNKNOWN"
        booking.error_message = str(e)
        trip_request.status = TripRequestStatus.FAILED

    db.commit()
    return booking


def select_option(
    db: Session,
    trip_request_id: UUID,
    strategy: str = "CHEAPEST",
) -> HotelOption | None:
    """
    Select the best hotel option based on strategy.

    Args:
        db: Database session
        trip_request_id: ID of the trip request
        strategy: Selection strategy (currently only CHEAPEST)

    Returns:
        Selected hotel option or None
    """
    query = db.query(HotelOption).filter(
        HotelOption.trip_request_id == trip_request_id
    )

    if strategy == "CHEAPEST":
        query = query.order_by(HotelOption.rank.asc())

    return query.first()


def build_payment_payload(payment_info: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Build Amadeus payment payload from payment info.

    Note: This data is passed through but never logged or stored.
    """
    payment_type = payment_info.get("type", "test")

    if payment_type == "test":
        # Test mode - use dummy card for sandbox
        return [
            {
                "id": 1,
                "method": "CREDIT_CARD",
                "card": {
                    "vendorCode": "VI",
                    "cardNumber": "4111111111111111",
                    "expiryDate": "2026-12",
                },
            }
        ]

    # Real card payment (for when moving to production)
    return [
        {
            "id": 1,
            "method": "CREDIT_CARD",
            "card": {
                "vendorCode": payment_info.get("vendorCode", "VI"),
                "cardNumber": payment_info.get("cardNumber", ""),
                "expiryDate": payment_info.get("expiryDate", ""),
            },
        }
    ]


def sanitize_response(response: dict[str, Any]) -> dict[str, Any]:
    """
    Remove sensitive information from Amadeus response before storing.
    """
    sanitized = dict(response)

    # Remove any payment information from the response
    if "data" in sanitized:
        data = dict(sanitized["data"])
        if "payments" in data:
            del data["payments"]
        sanitized["data"] = data

    return sanitized
