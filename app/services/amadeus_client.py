"""Amadeus Self-Service API client with token caching and retry logic."""

import threading
import time
from abc import ABC, abstractmethod
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings
from app.core.logging import get_logger, safe_log_dict

logger = get_logger(__name__)


class AmadeusError(Exception):
    """Base exception for Amadeus API errors."""

    def __init__(self, message: str, status_code: int | None = None, response: dict | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.response = response


class AmadeusAuthError(AmadeusError):
    """Authentication error (401)."""
    pass


class AmadeusRateLimitError(AmadeusError):
    """Rate limit error (429)."""
    pass


class AmadeusServerError(AmadeusError):
    """Server error (5xx)."""
    pass


class BaseAmadeusClient(ABC):
    """Abstract base class for Amadeus client."""

    @abstractmethod
    async def get_hotel_offers(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        adults: int = 1,
        max_price: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """Search for hotel offers by city."""
        pass

    @abstractmethod
    async def create_hotel_order(
        self,
        offer_id: str,
        guests: list[dict[str, Any]],
        payments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Create a hotel booking order."""
        pass


class AmadeusClient(BaseAmadeusClient):
    """Amadeus Self-Service API client with token caching and retry logic."""

    TOKEN_BUFFER_SECONDS = 60  # Refresh token 1 minute before expiry

    def __init__(
        self,
        client_id: str | None = None,
        client_secret: str | None = None,
        base_url: str | None = None,
    ):
        settings = get_settings()
        self.client_id = client_id or settings.AMADEUS_CLIENT_ID
        self.client_secret = client_secret or settings.AMADEUS_CLIENT_SECRET
        self.base_url = base_url or settings.AMADEUS_BASE_URL

        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        self._lock = threading.Lock()
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(30.0),
            )
        return self._http_client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def _fetch_new_token(self) -> str:
        """Fetch a new access token from Amadeus OAuth2 endpoint."""
        client = await self._get_http_client()

        logger.info("Fetching new Amadeus access token")
        response = await client.post(
            "/v1/security/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        if response.status_code != 200:
            logger.error(f"Failed to fetch token: {response.status_code}")
            raise AmadeusAuthError(
                f"Failed to fetch access token: {response.status_code}",
                status_code=response.status_code,
            )

        data = response.json()
        token = data["access_token"]
        expires_in = data.get("expires_in", 1799)  # Default 30 minutes

        with self._lock:
            self._token = token
            self._token_expires_at = datetime.now() + timedelta(seconds=expires_in - self.TOKEN_BUFFER_SECONDS)

        logger.info(f"Token fetched, expires in {expires_in}s")
        return token

    async def _get_valid_token(self) -> str:
        """Get a valid access token, refreshing if necessary."""
        with self._lock:
            if self._token and self._token_expires_at and datetime.now() < self._token_expires_at:
                return self._token

        return await self._fetch_new_token()

    async def _make_request(
        self,
        method: str,
        url: str,
        json_data: dict | None = None,
        params: dict | None = None,
        retry_on_auth: bool = True,
    ) -> dict[str, Any]:
        """Make an authenticated API request with retry logic."""
        client = await self._get_http_client()
        token = await self._get_valid_token()

        headers = {"Authorization": f"Bearer {token}"}

        # Log safe version of request
        if json_data:
            logger.debug(f"Request {method} {url}: {safe_log_dict(json_data)}")

        response = await client.request(
            method=method,
            url=url,
            json=json_data,
            params=params,
            headers=headers,
        )

        # Handle 401 - token expired, refresh and retry once
        if response.status_code == 401 and retry_on_auth:
            logger.warning("Token expired, refreshing and retrying")
            with self._lock:
                self._token = None
                self._token_expires_at = None
            return await self._make_request(method, url, json_data, params, retry_on_auth=False)

        # Handle rate limiting
        if response.status_code == 429:
            raise AmadeusRateLimitError(
                "Rate limited by Amadeus API",
                status_code=429,
                response=response.json() if response.content else None,
            )

        # Handle server errors
        if response.status_code >= 500:
            raise AmadeusServerError(
                f"Amadeus server error: {response.status_code}",
                status_code=response.status_code,
                response=response.json() if response.content else None,
            )

        # Handle other errors
        if response.status_code >= 400:
            error_data = response.json() if response.content else {}
            raise AmadeusError(
                f"Amadeus API error: {response.status_code}",
                status_code=response.status_code,
                response=error_data,
            )

        return response.json()

    @retry(
        retry=retry_if_exception_type((AmadeusRateLimitError, AmadeusServerError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def get_hotel_offers(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        adults: int = 1,
        max_price: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """
        Search for hotel offers by city.

        Uses the Hotel Search API to find available hotels and offers.
        """
        # First, get hotels in the city
        hotels_response = await self._make_request(
            "GET",
            "/v1/reference-data/locations/hotels/by-city",
            params={"cityCode": city_code},
        )

        hotel_ids = [h["hotelId"] for h in hotels_response.get("data", [])[:20]]  # Limit to 20 hotels

        if not hotel_ids:
            logger.warning(f"No hotels found in city {city_code}")
            return []

        # Get offers for these hotels
        params = {
            "hotelIds": ",".join(hotel_ids),
            "checkInDate": check_in.isoformat(),
            "checkOutDate": check_out.isoformat(),
            "adults": adults,
            "roomQuantity": 1,
        }

        if max_price:
            params["priceRange"] = f"0-{int(max_price)}"

        try:
            response = await self._make_request(
                "GET",
                "/v2/shopping/hotel-offers",
                params=params,
            )
            return response.get("data", [])
        except AmadeusError as e:
            if e.status_code == 400:
                # No offers available, not an error
                logger.info(f"No offers found for hotels in {city_code}")
                return []
            raise

    @retry(
        retry=retry_if_exception_type((AmadeusRateLimitError, AmadeusServerError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
    )
    async def create_hotel_order(
        self,
        offer_id: str,
        guests: list[dict[str, Any]],
        payments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Create a hotel booking order using /v2/booking/hotel-orders.

        Args:
            offer_id: The offer ID from hotel search
            guests: List of guest information
            payments: List of payment information (NOT logged or stored)

        Returns:
            Booking confirmation response
        """
        # First, get the full offer details to ensure it's still valid
        offer_response = await self._make_request(
            "GET",
            f"/v2/shopping/hotel-offers/{offer_id}",
        )

        offer_data = offer_response.get("data", {})

        # Build the booking request
        booking_request = {
            "data": {
                "type": "hotel-order",
                "guests": guests,
                "payments": payments,
                "rooms": [
                    {
                        "guestIds": [1],  # First guest
                        "paymentId": 1,
                        "specialRequest": "",
                    }
                ],
            }
        }

        # Log without payment details
        logger.info(f"Creating hotel order for offer {offer_id}")

        response = await self._make_request(
            "POST",
            "/v2/booking/hotel-orders",
            json_data=booking_request,
        )

        logger.info(f"Hotel order created successfully")
        return response


class MockAmadeusClient(BaseAmadeusClient):
    """Mock Amadeus client for testing."""

    def __init__(self, fail_booking: bool = False, no_offers: bool = False):
        self.fail_booking = fail_booking
        self.no_offers = no_offers
        self._call_count = 0
        self.hotel_offers_calls: list[dict] = []
        self.create_order_calls: list[dict] = []

    async def get_hotel_offers(
        self,
        city_code: str,
        check_in: date,
        check_out: date,
        adults: int = 1,
        max_price: Decimal | None = None,
    ) -> list[dict[str, Any]]:
        """Return mock hotel offers."""
        self.hotel_offers_calls.append({
            "city_code": city_code,
            "check_in": check_in,
            "check_out": check_out,
            "adults": adults,
            "max_price": max_price,
        })

        if self.no_offers:
            return []

        num_nights = (check_out - check_in).days

        # Generate deterministic mock offers
        offers = []
        for i in range(5):
            base_price = 100 + (i * 25) + (hash(city_code) % 50)
            total_price = base_price * num_nights

            # Filter by max price if provided
            if max_price and base_price > float(max_price):
                continue

            offers.append({
                "type": "hotel-offers",
                "hotel": {
                    "hotelId": f"MOCK{city_code}{i:03d}",
                    "name": f"Mock Hotel {city_code} {i + 1}",
                    "address": {
                        "lines": [f"{100 + i} Test Street"],
                        "cityName": city_code,
                    },
                },
                "offers": [
                    {
                        "id": f"OFFER{city_code}{check_in.isoformat()}{i:03d}",
                        "checkInDate": check_in.isoformat(),
                        "checkOutDate": check_out.isoformat(),
                        "price": {
                            "currency": "USD",
                            "total": str(total_price),
                            "base": str(total_price),
                        },
                        "room": {
                            "type": "STANDARD",
                            "description": {"text": "Standard Room"},
                        },
                    }
                ],
            })

        return offers

    async def create_hotel_order(
        self,
        offer_id: str,
        guests: list[dict[str, Any]],
        payments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return mock booking response."""
        self._call_count += 1
        self.create_order_calls.append({
            "offer_id": offer_id,
            "guests": guests,
            # Don't store payments even in mock
        })

        if self.fail_booking:
            raise AmadeusError(
                "Booking failed",
                status_code=400,
                response={"errors": [{"detail": "Mock booking failure"}]},
            )

        return {
            "data": {
                "type": "hotel-order",
                "id": f"ORDER{self._call_count:06d}",
                "reference": f"REF{self._call_count:06d}",
                "guests": guests,
                "hotel": {
                    "hotelId": offer_id.split("OFFER")[1][:6] if "OFFER" in offer_id else "UNKNOWN",
                    "name": "Mock Hotel",
                },
            }
        }
