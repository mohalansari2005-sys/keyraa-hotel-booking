"""Trip request routes."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.api.deps import DBSession, TenantId
from app.models.hotel_option import HotelOption
from app.models.trip_request import TripRequest
from app.schemas.hotel_option import HotelOptionBrief, TripRequestOptionsResponse

router = APIRouter(prefix="/v1/trip-requests", tags=["trip-requests"])


@router.get("/{trip_request_id}/options", response_model=TripRequestOptionsResponse)
async def get_trip_request_options(
    db: DBSession,
    tenant_id: TenantId,
    trip_request_id: UUID,
) -> TripRequestOptionsResponse:
    """Get hotel options for a trip request, ranked by price."""
    # Get trip request
    result = await db.execute(
        select(TripRequest)
        .options(joinedload(TripRequest.hotel_options))
        .where(
            TripRequest.id == trip_request_id,
            TripRequest.tenant_id == tenant_id,
        )
    )
    trip_request = result.unique().scalar_one_or_none()

    if not trip_request:
        raise HTTPException(status_code=404, detail="Trip request not found")

    # Build options list (already sorted by rank)
    options = sorted(trip_request.hotel_options, key=lambda x: x.rank)

    option_briefs = [
        HotelOptionBrief(
            hotel_id=opt.hotel_id,
            offer_id=opt.offer_id,
            hotel_name=opt.hotel_name,
            address=opt.address,
            price_total=opt.price_total,
            price_per_night=opt.price_per_night,
            currency=opt.currency,
            rank=opt.rank,
        )
        for opt in options
    ]

    return TripRequestOptionsResponse(
        trip_request_id=trip_request.id,
        city=trip_request.city,
        check_in=str(trip_request.check_in),
        check_out=str(trip_request.check_out),
        options=option_briefs,
    )
