"""Email service for sending booking notifications."""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger
from app.models.booking import Booking
from app.models.employee import Employee
from app.models.trip_request import TripRequest

logger = get_logger(__name__)


class EmailService:
    """Service for sending booking notification emails."""

    def __init__(
        self,
        smtp_host: str | None = None,
        smtp_port: int | None = None,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        email_from: str | None = None,
    ):
        settings = get_settings()
        self.smtp_host = smtp_host or settings.SMTP_HOST
        self.smtp_port = smtp_port or settings.SMTP_PORT
        self.smtp_user = smtp_user or settings.SMTP_USER
        self.smtp_password = smtp_password or settings.SMTP_PASSWORD
        self.email_from = email_from or settings.EMAIL_FROM

    def send_booking_confirmation(
        self,
        employee: Employee,
        booking: Booking,
    ) -> bool:
        """
        Send booking confirmation email to employee.

        Args:
            employee: Employee who made the booking
            booking: Confirmed booking details

        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"Hotel Booking Confirmed - {booking.hotel_name}"

        text_content = self._render_confirmation_text(employee, booking)
        html_content = self._render_confirmation_html(employee, booking)

        return self._send_email(
            to_email=employee.email,
            to_name=employee.name,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )

    def send_booking_failure(
        self,
        employee: Employee,
        trip_request: TripRequest,
        reason: str,
    ) -> bool:
        """
        Send booking failure notification to employee.

        Args:
            employee: Employee whose booking failed
            trip_request: The trip request that failed
            reason: Reason for failure

        Returns:
            True if email sent successfully, False otherwise
        """
        subject = f"Hotel Booking Failed - {trip_request.city}"

        text_content = self._render_failure_text(employee, trip_request, reason)
        html_content = self._render_failure_html(employee, trip_request, reason)

        return self._send_email(
            to_email=employee.email,
            to_name=employee.name,
            subject=subject,
            text_content=text_content,
            html_content=html_content,
        )

    def _send_email(
        self,
        to_email: str,
        to_name: str,
        subject: str,
        text_content: str,
        html_content: str,
    ) -> bool:
        """Send email via SMTP with TLS support for Gmail."""
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"Keyraa Bookings <{self.email_from}>"
            msg["To"] = f"{to_name} <{to_email}>"

            # Attach text and HTML versions
            msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            # Connect and send with TLS
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.ehlo()
                # Use STARTTLS for secure connection (required for Gmail)
                if self.smtp_port == 587:
                    server.starttls()
                    server.ehlo()
                if self.smtp_user and self.smtp_password:
                    server.login(self.smtp_user, self.smtp_password)
                server.send_message(msg)

            logger.info(f"Email sent successfully to {to_email}")
            return True

        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False


    def _render_confirmation_text(
        self,
        employee: Employee,
        booking: Booking,
    ) -> str:
        """Render confirmation email as plain text."""
        return f"""
Hello {employee.name},

Your hotel booking has been confirmed!

BOOKING DETAILS
===============
Hotel: {booking.hotel_name}
Address: {booking.hotel_address or 'N/A'}
Check-in: {booking.check_in}
Check-out: {booking.check_out}
Total Price: {booking.currency} {booking.total_price}

CONFIRMATION
============
Booking Reference: {booking.amadeus_reference or 'N/A'}
Order ID: {booking.amadeus_order_id or 'N/A'}

Thank you for using Keyraa!

Best regards,
The Keyraa Team
        """.strip()

    def _render_confirmation_html(
        self,
        employee: Employee,
        booking: Booking,
    ) -> str:
        """Render confirmation email as HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #4F46E5; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }}
        .details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .details h3 {{ margin-top: 0; color: #4F46E5; }}
        .confirmation {{ background: #10B981; color: white; padding: 15px; border-radius: 8px; text-align: center; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Booking Confirmed!</h1>
        </div>
        <div class="content">
            <p>Hello {employee.name},</p>
            <p>Your hotel booking has been confirmed!</p>
            
            <div class="details">
                <h3>Booking Details</h3>
                <p><strong>Hotel:</strong> {booking.hotel_name}</p>
                <p><strong>Address:</strong> {booking.hotel_address or 'N/A'}</p>
                <p><strong>Check-in:</strong> {booking.check_in}</p>
                <p><strong>Check-out:</strong> {booking.check_out}</p>
                <p><strong>Total Price:</strong> {booking.currency} {booking.total_price}</p>
            </div>
            
            <div class="confirmation">
                <p style="margin: 0;"><strong>Booking Reference:</strong> {booking.amadeus_reference or 'N/A'}</p>
                <p style="margin: 0;"><strong>Order ID:</strong> {booking.amadeus_order_id or 'N/A'}</p>
            </div>
        </div>
        <div class="footer">
            <p>Thank you for using Keyraa!</p>
            <p>Best regards,<br>The Keyraa Team</p>
        </div>
    </div>
</body>
</html>
        """.strip()

    def _render_failure_text(
        self,
        employee: Employee,
        trip_request: TripRequest,
        reason: str,
    ) -> str:
        """Render failure email as plain text."""
        return f"""
Hello {employee.name},

Unfortunately, we were unable to complete your hotel booking.

TRIP DETAILS
============
Destination: {trip_request.city}
Check-in: {trip_request.check_in}
Check-out: {trip_request.check_out}
Budget: {trip_request.max_nightly_budget} per night

REASON
======
{reason}

Please contact your travel administrator for assistance.

Best regards,
The Keyraa Team
        """.strip()

    def _render_failure_html(
        self,
        employee: Employee,
        trip_request: TripRequest,
        reason: str,
    ) -> str:
        """Render failure email as HTML."""
        return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .header {{ background: #EF4444; color: white; padding: 20px; text-align: center; border-radius: 8px 8px 0 0; }}
        .content {{ background: #f9fafb; padding: 20px; border: 1px solid #e5e7eb; }}
        .details {{ background: white; padding: 15px; border-radius: 8px; margin: 15px 0; }}
        .details h3 {{ margin-top: 0; color: #374151; }}
        .reason {{ background: #FEF2F2; border: 1px solid #FECACA; padding: 15px; border-radius: 8px; color: #991B1B; }}
        .footer {{ text-align: center; padding: 20px; color: #6b7280; font-size: 14px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Booking Failed</h1>
        </div>
        <div class="content">
            <p>Hello {employee.name},</p>
            <p>Unfortunately, we were unable to complete your hotel booking.</p>
            
            <div class="details">
                <h3>Trip Details</h3>
                <p><strong>Destination:</strong> {trip_request.city}</p>
                <p><strong>Check-in:</strong> {trip_request.check_in}</p>
                <p><strong>Check-out:</strong> {trip_request.check_out}</p>
                <p><strong>Budget:</strong> {trip_request.max_nightly_budget} per night</p>
            </div>
            
            <div class="reason">
                <strong>Reason:</strong> {reason}
            </div>
            
            <p>Please contact your travel administrator for assistance.</p>
        </div>
        <div class="footer">
            <p>Best regards,<br>The Keyraa Team</p>
        </div>
    </div>
</body>
</html>
        """.strip()


# Default email service instance
_email_service: EmailService | None = None


def get_email_service() -> EmailService:
    """Get the email service instance."""
    global _email_service
    if _email_service is None:
        _email_service = EmailService()
    return _email_service
