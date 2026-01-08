"""Tests for option service."""

from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.services.option_service import parse_and_rank_offers


class TestParseAndRankOffers:
    """Tests for offer parsing and ranking."""

    def test_parse_single_offer(self):
        """Test parsing a single offer."""
        raw_offers = [
            {
                "hotel": {
                    "hotelId": "HILPAR001",
                    "name": "Hilton Paris",
                    "address": {
                        "lines": ["123 Champs-Élysées"],
                        "cityName": "Paris",
                    },
                },
                "offers": [
                    {
                        "id": "OFFER123",
                        "price": {
                            "total": "400.00",
                            "currency": "EUR",
                        },
                    }
                ],
            }
        ]

        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)  # 2 nights

        result = parse_and_rank_offers(
            raw_offers,
            check_in,
            check_out,
            max_nightly_budget=Decimal("250.00"),
        )

        assert len(result) == 1
        assert result[0]["hotel_id"] == "HILPAR001"
        assert result[0]["hotel_name"] == "Hilton Paris"
        assert result[0]["offer_id"] == "OFFER123"
        assert result[0]["price_total"] == Decimal("400.00")
        assert result[0]["price_per_night"] == Decimal("200.00")
        assert result[0]["currency"] == "EUR"
        assert "123 Champs-Élysées" in result[0]["address"]

    def test_rank_by_price(self):
        """Test that offers are ranked by price (cheapest first)."""
        raw_offers = [
            {
                "hotel": {"hotelId": "HOTEL_C", "name": "Expensive Hotel"},
                "offers": [{"id": "OFFER_C", "price": {"total": "600.00", "currency": "EUR"}}],
            },
            {
                "hotel": {"hotelId": "HOTEL_A", "name": "Cheap Hotel"},
                "offers": [{"id": "OFFER_A", "price": {"total": "200.00", "currency": "EUR"}}],
            },
            {
                "hotel": {"hotelId": "HOTEL_B", "name": "Medium Hotel"},
                "offers": [{"id": "OFFER_B", "price": {"total": "400.00", "currency": "EUR"}}],
            },
        ]

        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        result = parse_and_rank_offers(
            raw_offers,
            check_in,
            check_out,
            max_nightly_budget=Decimal("500.00"),
        )

        assert len(result) == 3
        assert result[0]["hotel_name"] == "Cheap Hotel"
        assert result[1]["hotel_name"] == "Medium Hotel"
        assert result[2]["hotel_name"] == "Expensive Hotel"

    def test_filter_by_budget(self):
        """Test that offers exceeding budget are filtered out."""
        raw_offers = [
            {
                "hotel": {"hotelId": "HOTEL_A", "name": "Cheap Hotel"},
                "offers": [{"id": "OFFER_A", "price": {"total": "200.00", "currency": "EUR"}}],
            },
            {
                "hotel": {"hotelId": "HOTEL_B", "name": "Expensive Hotel"},
                "offers": [{"id": "OFFER_B", "price": {"total": "600.00", "currency": "EUR"}}],
            },
        ]

        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)  # 2 nights

        # Budget of 150 per night = 300 total max
        result = parse_and_rank_offers(
            raw_offers,
            check_in,
            check_out,
            max_nightly_budget=Decimal("150.00"),
        )

        assert len(result) == 1
        assert result[0]["hotel_name"] == "Cheap Hotel"

    def test_empty_offers(self):
        """Test handling empty offers."""
        result = parse_and_rank_offers(
            [],
            date.today() + timedelta(days=30),
            date.today() + timedelta(days=32),
            max_nightly_budget=Decimal("200.00"),
        )

        assert len(result) == 0

    def test_deterministic_sorting(self):
        """Test that sorting is deterministic for same price."""
        raw_offers = [
            {
                "hotel": {"hotelId": "HOTEL_B", "name": "Hotel B"},
                "offers": [{"id": "OFFER_B", "price": {"total": "200.00", "currency": "EUR"}}],
            },
            {
                "hotel": {"hotelId": "HOTEL_A", "name": "Hotel A"},
                "offers": [{"id": "OFFER_A", "price": {"total": "200.00", "currency": "EUR"}}],
            },
        ]

        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        # Run multiple times to ensure determinism
        for _ in range(5):
            result = parse_and_rank_offers(
                raw_offers,
                check_in,
                check_out,
                max_nightly_budget=Decimal("200.00"),
            )

            # Should be sorted by hotel_id when prices are equal
            assert result[0]["hotel_id"] == "HOTEL_A"
            assert result[1]["hotel_id"] == "HOTEL_B"

    def test_missing_address(self):
        """Test handling offers without address."""
        raw_offers = [
            {
                "hotel": {"hotelId": "HOTEL_A", "name": "Hotel A"},
                "offers": [{"id": "OFFER_A", "price": {"total": "200.00", "currency": "EUR"}}],
            },
        ]

        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        result = parse_and_rank_offers(
            raw_offers,
            check_in,
            check_out,
            max_nightly_budget=Decimal("200.00"),
        )

        assert len(result) == 1
        assert result[0]["address"] is None or result[0]["address"] == ""
