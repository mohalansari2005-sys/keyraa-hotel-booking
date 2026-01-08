"""Tests for Amadeus client."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.amadeus_client import (
    AmadeusAuthError,
    AmadeusClient,
    AmadeusError,
    AmadeusRateLimitError,
    MockAmadeusClient,
)


class TestMockAmadeusClient:
    """Tests for the mock Amadeus client."""

    @pytest.mark.asyncio
    async def test_get_hotel_offers(self, mock_amadeus_client: MockAmadeusClient):
        """Test getting hotel offers from mock client."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        offers = await mock_amadeus_client.get_hotel_offers(
            city_code="PAR",
            check_in=check_in,
            check_out=check_out,
        )

        assert len(offers) == 5
        assert offers[0]["hotel"]["name"].startswith("Mock Hotel")
        assert "offers" in offers[0]

    @pytest.mark.asyncio
    async def test_get_hotel_offers_no_offers(
        self, mock_amadeus_client_no_offers: MockAmadeusClient
    ):
        """Test getting no offers from mock client."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        offers = await mock_amadeus_client_no_offers.get_hotel_offers(
            city_code="PAR",
            check_in=check_in,
            check_out=check_out,
        )

        assert len(offers) == 0

    @pytest.mark.asyncio
    async def test_get_hotel_offers_with_budget(
        self, mock_amadeus_client: MockAmadeusClient
    ):
        """Test filtering offers by budget."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        offers = await mock_amadeus_client.get_hotel_offers(
            city_code="PAR",
            check_in=check_in,
            check_out=check_out,
            max_price=Decimal("110"),  # Low budget, should filter some
        )

        # Should have fewer offers due to budget filter
        assert len(offers) <= 5

    @pytest.mark.asyncio
    async def test_create_hotel_order_success(
        self, mock_amadeus_client: MockAmadeusClient
    ):
        """Test successful hotel order creation."""
        result = await mock_amadeus_client.create_hotel_order(
            offer_id="OFFER123",
            guests=[{"id": 1, "name": {"firstName": "John", "lastName": "Doe"}}],
            payments=[{"id": 1, "method": "CREDIT_CARD"}],
        )

        assert "data" in result
        assert result["data"]["type"] == "hotel-order"
        assert result["data"]["id"].startswith("ORDER")
        assert result["data"]["reference"].startswith("REF")

    @pytest.mark.asyncio
    async def test_create_hotel_order_failure(
        self, mock_amadeus_client_fail_booking: MockAmadeusClient
    ):
        """Test failed hotel order creation."""
        with pytest.raises(AmadeusError) as exc_info:
            await mock_amadeus_client_fail_booking.create_hotel_order(
                offer_id="OFFER123",
                guests=[{"id": 1, "name": {"firstName": "John", "lastName": "Doe"}}],
                payments=[{"id": 1, "method": "CREDIT_CARD"}],
            )

        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_call_tracking(self, mock_amadeus_client: MockAmadeusClient):
        """Test that mock client tracks API calls."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        await mock_amadeus_client.get_hotel_offers(
            city_code="PAR",
            check_in=check_in,
            check_out=check_out,
        )

        assert len(mock_amadeus_client.hotel_offers_calls) == 1
        assert mock_amadeus_client.hotel_offers_calls[0]["city_code"] == "PAR"


class TestAmadeusClientTokenCaching:
    """Tests for Amadeus client token caching."""

    @pytest.mark.asyncio
    async def test_token_caching(self):
        """Test that token is cached and reused."""
        client = AmadeusClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "test_token",
            "expires_in": 1799,
        }

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.post.return_value = mock_response
            mock_get_client.return_value = mock_http

            # First call should fetch token
            token1 = await client._get_valid_token()
            assert token1 == "test_token"
            assert mock_http.post.call_count == 1

            # Second call should use cached token
            token2 = await client._get_valid_token()
            assert token2 == "test_token"
            assert mock_http.post.call_count == 1  # Still only one call

        await client.close()


class TestAmadeusClientRetry:
    """Tests for Amadeus client retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_401_refreshes_token(self):
        """Test that 401 triggers token refresh and retry."""
        client = AmadeusClient(
            client_id="test_id",
            client_secret="test_secret",
        )

        call_count = 0

        async def mock_request(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            
            # First request: return token
            if call_count == 1:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {
                    "access_token": "old_token",
                    "expires_in": 1799,
                }
                return response
            
            # Second request (actual API call): return 401
            if call_count == 2:
                response = MagicMock()
                response.status_code = 401
                return response
            
            # Third request: return new token
            if call_count == 3:
                response = MagicMock()
                response.status_code = 200
                response.json.return_value = {
                    "access_token": "new_token",
                    "expires_in": 1799,
                }
                return response
            
            # Fourth request: success
            response = MagicMock()
            response.status_code = 200
            response.json.return_value = {"data": []}
            response.content = True
            return response

        with patch.object(client, "_get_http_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.post = mock_request
            mock_http.request = mock_request
            mock_get_client.return_value = mock_http

            result = await client._make_request("GET", "/test")
            assert result == {"data": []}
            assert call_count == 4  # Token, failed request, new token, retry

        await client.close()
