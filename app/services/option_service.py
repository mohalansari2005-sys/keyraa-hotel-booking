"""Option service for processing hotel options."""

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.hotel_option import HotelOption
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.amadeus_client import BaseAmadeusClient

logger = get_logger(__name__)


async def fetch_and_store_options(
    db: Session,
    trip_request: TripRequest,
    amadeus_client: BaseAmadeusClient,
    max_options: int = 5,
) -> int:
    """
    Fetch hotel options from Amadeus and store the top options.

    Args:
        db: Database session
        trip_request: The trip request to fetch options for
        amadeus_client: Amadeus API client
        max_options: Maximum number of options to store (2-5)

    Returns:
        Number of options stored
    """
    logger.info(
        f"Fetching options for trip request {trip_request.id}: "
        f"{trip_request.city} {trip_request.check_in} to {trip_request.check_out}"
    )

    # Delete existing options for this trip request
    db.execute(
        select(HotelOption).where(HotelOption.trip_request_id == trip_request.id)
    )
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


def parse_and_rank_offers(
    raw_offers: list[dict[str, Any]],
    check_in: date,
    check_out: date,
    max_nightly_budget: Decimal,
) -> list[dict[str, Any]]:
    """
    Parse Amadeus offer responses and rank by price (cheapest first).

    Args:
        raw_offers: Raw offers from Amadeus API
        check_in: Check-in date
        check_out: Check-out date
        max_nightly_budget: Maximum price per night

    Returns:
        List of parsed offers, sorted by price
    """
    num_nights = (check_out - check_in).days
    if num_nights <= 0:
        num_nights = 1

    parsed = []
    for hotel_offer in raw_offers:
        hotel = hotel_offer.get("hotel", {})
        offers = hotel_offer.get("offers", [])

        for offer in offers:
            price_info = offer.get("price", {})
            total_str = price_info.get("total", "0")

            try:
                total = Decimal(total_str)
            except (ValueError, TypeError):
                continue

            per_night = total / num_nights

            # Filter by budget
            if per_night > max_nightly_budget:
                continue

            # Build address string
            address_parts = hotel.get("address", {})
            address_lines = address_parts.get("lines", [])
            city = address_parts.get("cityName", "")
            address = ", ".join(address_lines + [city]) if address_lines else city

            parsed.append({
                "hotel_id": hotel.get("hotelId", ""),
                "offer_id": offer.get("id", ""),
                "hotel_name": hotel.get("name", "Unknown Hotel"),
                "address": address or None,
                "price_total": total,
                "price_per_night": per_night,
                "currency": price_info.get("currency", "USD"),
                "raw_offer": offer,
            })

    # Sort by total price (deterministic - cheapest first)
    parsed.sort(key=lambda x: (x["price_total"], x["hotel_id"], x["offer_id"]))

    return parsed
