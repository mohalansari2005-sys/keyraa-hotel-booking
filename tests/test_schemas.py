"""Tests for Pydantic schemas."""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.employee import EmployeeCreate
from app.schemas.trip_request import TripRequestCreate
from app.schemas.bulk_job import PaymentInfo


class TestEmployeeSchema:
    """Tests for employee schemas."""

    def test_valid_employee(self):
        """Test creating a valid employee."""
        employee = EmployeeCreate(
            employee_ref="EMP001",
            name="John Doe",
            email="john@example.com",
        )
        assert employee.employee_ref == "EMP001"
        assert employee.name == "John Doe"
        assert employee.email == "john@example.com"

    def test_invalid_email(self):
        """Test that invalid email raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            EmployeeCreate(
                employee_ref="EMP001",
                name="John Doe",
                email="not-an-email",
            )
        assert "email" in str(exc_info.value).lower()

    def test_empty_employee_ref(self):
        """Test that empty employee_ref raises validation error."""
        with pytest.raises(ValidationError):
            EmployeeCreate(
                employee_ref="",
                name="John Doe",
                email="john@example.com",
            )

    def test_empty_name(self):
        """Test that empty name raises validation error."""
        with pytest.raises(ValidationError):
            EmployeeCreate(
                employee_ref="EMP001",
                name="",
                email="john@example.com",
            )


class TestTripRequestSchema:
    """Tests for trip request schemas."""

    def test_valid_trip_request(self):
        """Test creating a valid trip request."""
        trip = TripRequestCreate(
            employee_ref="EMP001",
            city="PAR",
            check_in=date.today() + timedelta(days=30),
            check_out=date.today() + timedelta(days=32),
            max_nightly_budget=Decimal("200.00"),
        )
        assert trip.employee_ref == "EMP001"
        assert trip.city == "PAR"
        assert trip.max_nightly_budget == Decimal("200.00")

    def test_city_uppercase(self):
        """Test that city code is converted to uppercase."""
        trip = TripRequestCreate(
            employee_ref="EMP001",
            city="par",
            check_in=date.today() + timedelta(days=30),
            check_out=date.today() + timedelta(days=32),
            max_nightly_budget=Decimal("200.00"),
        )
        assert trip.city == "PAR"

    def test_check_in_after_check_out(self):
        """Test that check_in must be before check_out."""
        with pytest.raises(ValidationError) as exc_info:
            TripRequestCreate(
                employee_ref="EMP001",
                city="PAR",
                check_in=date.today() + timedelta(days=32),
                check_out=date.today() + timedelta(days=30),
                max_nightly_budget=Decimal("200.00"),
            )
        assert "check_in must be before check_out" in str(exc_info.value)

    def test_same_check_in_check_out(self):
        """Test that check_in must not equal check_out."""
        same_date = date.today() + timedelta(days=30)
        with pytest.raises(ValidationError) as exc_info:
            TripRequestCreate(
                employee_ref="EMP001",
                city="PAR",
                check_in=same_date,
                check_out=same_date,
                max_nightly_budget=Decimal("200.00"),
            )
        assert "check_in must be before check_out" in str(exc_info.value)

    def test_negative_budget(self):
        """Test that negative budget raises validation error."""
        with pytest.raises(ValidationError):
            TripRequestCreate(
                employee_ref="EMP001",
                city="PAR",
                check_in=date.today() + timedelta(days=30),
                check_out=date.today() + timedelta(days=32),
                max_nightly_budget=Decimal("-100.00"),
            )

    def test_zero_budget(self):
        """Test that zero budget raises validation error."""
        with pytest.raises(ValidationError):
            TripRequestCreate(
                employee_ref="EMP001",
                city="PAR",
                check_in=date.today() + timedelta(days=30),
                check_out=date.today() + timedelta(days=32),
                max_nightly_budget=Decimal("0"),
            )


class TestPaymentSchema:
    """Tests for payment schemas."""

    def test_test_payment(self):
        """Test creating a test payment."""
        payment = PaymentInfo(type="test", token="test-token")
        assert payment.type == "test"
        assert payment.token == "test-token"

    def test_payment_aliases(self):
        """Test that payment fields support aliases."""
        payment = PaymentInfo(
            type="card",
            vendorCode="VI",
            cardNumber="4111111111111111",
            expiryDate="2026-12",
        )
        assert payment.card_vendor_code == "VI"
        assert payment.card_number == "4111111111111111"
        assert payment.expiry_date == "2026-12"
