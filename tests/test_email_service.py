"""Tests for email service."""

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid

import pytest

from app.models.booking import Booking, BookingStatus
from app.models.employee import Employee
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.email_service import EmailService


@pytest.fixture
def email_service():
    """Create email service for testing."""
    return EmailService(
        smtp_host="localhost",
        smtp_port=1025,
        email_from="test@keyraa.local",
    )


@pytest.fixture
def mock_employee():
    """Create a mock employee."""
    employee = MagicMock(spec=Employee)
    employee.id = uuid.uuid4()
    employee.name = "John Doe"
    employee.email = "john@example.com"
    employee.employee_ref = "EMP001"
    return employee


@pytest.fixture
def mock_booking(mock_employee):
    """Create a mock booking."""
    booking = MagicMock(spec=Booking)
    booking.id = uuid.uuid4()
    booking.hotel_name = "Test Hotel Paris"
    booking.hotel_address = "123 Test Street, Paris"
    booking.check_in = date.today() + timedelta(days=30)
    booking.check_out = date.today() + timedelta(days=32)
    booking.total_price = Decimal("350.00")
    booking.currency = "EUR"
    booking.amadeus_reference = "REF123456"
    booking.amadeus_order_id = "ORDER123456"
    booking.status = BookingStatus.CONFIRMED
    return booking


@pytest.fixture
def mock_trip_request():
    """Create a mock trip request."""
    trip = MagicMock(spec=TripRequest)
    trip.id = uuid.uuid4()
    trip.city = "PAR"
    trip.check_in = date.today() + timedelta(days=30)
    trip.check_out = date.today() + timedelta(days=32)
    trip.max_nightly_budget = Decimal("200.00")
    trip.status = TripRequestStatus.FAILED
    return trip


class TestEmailTemplates:
    """Tests for email template rendering."""

    def test_confirmation_text(self, email_service, mock_employee, mock_booking):
        """Test confirmation email text template."""
        text = email_service._render_confirmation_text(mock_employee, mock_booking)

        assert "John Doe" in text
        assert "Test Hotel Paris" in text
        assert "123 Test Street, Paris" in text
        assert "REF123456" in text
        assert "ORDER123456" in text
        assert "350" in text
        assert "EUR" in text

    def test_confirmation_html(self, email_service, mock_employee, mock_booking):
        """Test confirmation email HTML template."""
        html = email_service._render_confirmation_html(mock_employee, mock_booking)

        assert "John Doe" in html
        assert "Test Hotel Paris" in html
        assert "REF123456" in html
        assert "Booking Confirmed" in html
        assert "<html>" in html
        assert "</html>" in html

    def test_failure_text(self, email_service, mock_employee, mock_trip_request):
        """Test failure email text template."""
        text = email_service._render_failure_text(
            mock_employee, mock_trip_request, "No hotels available"
        )

        assert "John Doe" in text
        assert "PAR" in text
        assert "No hotels available" in text
        assert "Unfortunately" in text

    def test_failure_html(self, email_service, mock_employee, mock_trip_request):
        """Test failure email HTML template."""
        html = email_service._render_failure_html(
            mock_employee, mock_trip_request, "No hotels available"
        )

        assert "John Doe" in html
        assert "PAR" in html
        assert "No hotels available" in html
        assert "Booking Failed" in html
        assert "<html>" in html

    def test_missing_address_handled(self, email_service, mock_employee, mock_booking):
        """Test that missing address is handled gracefully."""
        mock_booking.hotel_address = None

        text = email_service._render_confirmation_text(mock_employee, mock_booking)
        assert "N/A" in text or "None" not in text

    def test_missing_reference_handled(
        self, email_service, mock_employee, mock_booking
    ):
        """Test that missing reference is handled gracefully."""
        mock_booking.amadeus_reference = None

        text = email_service._render_confirmation_text(mock_employee, mock_booking)
        # Should still render without error
        assert "John Doe" in text


class TestEmailSending:
    """Tests for email sending functionality."""

    def test_send_confirmation_success(
        self, email_service, mock_employee, mock_booking
    ):
        """Test successful email sending."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_service.send_booking_confirmation(
                mock_employee, mock_booking
            )

            assert result is True
            mock_server.send_message.assert_called_once()

    def test_send_confirmation_failure(
        self, email_service, mock_employee, mock_booking
    ):
        """Test email sending failure handling."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.side_effect = Exception("SMTP connection failed")

            result = email_service.send_booking_confirmation(
                mock_employee, mock_booking
            )

            assert result is False

    def test_send_failure_notification(
        self, email_service, mock_employee, mock_trip_request
    ):
        """Test sending failure notification."""
        with patch("smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = email_service.send_booking_failure(
                mock_employee, mock_trip_request, "No options available"
            )

            assert result is True
            mock_server.send_message.assert_called_once()
