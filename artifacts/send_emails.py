#!/usr/bin/env python3
"""
Send booking confirmation emails via Resend API.
This script sends emails for the bookings that were already created.
"""

import resend
import sys
from datetime import datetime

# Resend API Key
RESEND_API_KEY = "re_4Lib65iC_ASEzMWnQfP4pffs5XLZageNW"
resend.api_key = RESEND_API_KEY

# Booking data from E2E test
BOOKINGS = [
    {
        "employee_name": "Mohammed Alansari",
        "employee_email": "moh.alansari2005@gmail.com",
        "hotel_name": "Mock Hotel PAR 1",
        "hotel_address": "100 Test Street, PAR",
        "check_in": "2026-03-01",
        "check_out": "2026-03-03",
        "total_price": "288.00",
        "currency": "USD",
        "amadeus_reference": "REF000001",
        "amadeus_order_id": "ORDER000001",
        "city": "PAR",
    },
    {
        "employee_name": "Majara Contact",
        "employee_email": "m.alansari@majaracapital.com",
        "hotel_name": "Mock Hotel LON 1",
        "hotel_address": "100 Test Street, LON",
        "check_in": "2026-03-05",
        "check_out": "2026-03-08",
        "total_price": "342.00",
        "currency": "USD",
        "amadeus_reference": "REF000002",
        "amadeus_order_id": "ORDER000002",
        "city": "LON",
    },
    {
        "employee_name": "John Doe",
        "employee_email": "john.doe@example.com",
        "hotel_name": "Mock Hotel PAR 1",
        "hotel_address": "100 Test Street, PAR",
        "check_in": "2026-03-02",
        "check_out": "2026-03-06",
        "total_price": "576.00",
        "currency": "USD",
        "amadeus_reference": "REF000003",
        "amadeus_order_id": "ORDER000003",
        "city": "PAR",
    },
]


def render_html(booking: dict) -> str:
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
            <h1>🏨 Booking Confirmed!</h1>
        </div>
        <div class="content">
            <p>Hello {booking['employee_name']},</p>
            <p>Your hotel booking has been confirmed!</p>
            
            <div class="details">
                <h3>Booking Details</h3>
                <p><strong>Hotel:</strong> {booking['hotel_name']}</p>
                <p><strong>Address:</strong> {booking['hotel_address']}</p>
                <p><strong>Check-in:</strong> {booking['check_in']}</p>
                <p><strong>Check-out:</strong> {booking['check_out']}</p>
                <p><strong>Total Price:</strong> {booking['currency']} {booking['total_price']}</p>
            </div>
            
            <div class="confirmation">
                <p style="margin: 0;"><strong>Booking Reference:</strong> {booking['amadeus_reference']}</p>
                <p style="margin: 0;"><strong>Order ID:</strong> {booking['amadeus_order_id']}</p>
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


def send_email(booking: dict) -> dict:
    """Send confirmation email via Resend."""
    html_content = render_html(booking)
    
    params = {
        "from": "Keyraa Bookings <onboarding@resend.dev>",
        "to": [booking["employee_email"]],
        "subject": f"Hotel Booking Confirmed - {booking['hotel_name']}",
        "html": html_content,
    }
    
    try:
        response = resend.Emails.send(params)
        return {
            "success": True,
            "recipient": booking["employee_email"],
            "subject": params["subject"],
            "message_id": response.get("id"),
            "timestamp": datetime.now().isoformat(),
            "booking_reference": booking["amadeus_reference"],
        }
    except Exception as e:
        return {
            "success": False,
            "recipient": booking["employee_email"],
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


def main():
    print("=" * 60)
    print("SENDING BOOKING CONFIRMATION EMAILS VIA RESEND")
    print("=" * 60)
    
    results = []
    
    for i, booking in enumerate(BOOKINGS, 1):
        print(f"\n[{i}/3] Sending to: {booking['employee_email']}")
        result = send_email(booking)
        results.append(result)
        
        if result["success"]:
            print(f"  ✅ SUCCESS")
            print(f"  📧 Message ID: {result['message_id']}")
            print(f"  📋 Reference: {result['booking_reference']}")
            print(f"  ⏰ Timestamp: {result['timestamp']}")
        else:
            print(f"  ❌ FAILED: {result['error']}")
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    
    success_count = sum(1 for r in results if r["success"])
    print(f"Total: {len(results)}, Success: {success_count}, Failed: {len(results) - success_count}")
    
    # Save results to file
    import json
    with open("/Users/mohammed/Desktop/Keyraa poc/artifacts/email_delivery_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: artifacts/email_delivery_results.json")
    
    return results


if __name__ == "__main__":
    main()
