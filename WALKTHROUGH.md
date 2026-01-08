# Keyraa Hotel Booking Backend PoC - E2E Walkthrough

**Test Date**: 2026-01-07  
**API Base URL**: http://localhost:8000  
**Tenant ID**: `11111111-1111-1111-1111-111111111111`

---

## Preconditions

### Services Started
| Service | Status | Port |
|---------|--------|------|
| PostgreSQL 15 | ✅ Running | 5432 |
| Redis | ✅ Running | 6379 |
| FastAPI (uvicorn) | ✅ Running | 8000 |
| Celery Worker | ✅ Running | - |

### Environment Configuration (.env)
```ini
# Database
DATABASE_URL=postgresql+asyncpg://keyraa@localhost:5432/keyraa
DATABASE_URL_SYNC=postgresql://keyraa@localhost:5432/keyraa

# Redis
REDIS_URL=redis://localhost:6379/0

# Email - Resend API (used for delivery)
RESEND_API_KEY=****

# Amadeus - Mock Mode
USE_MOCK_AMADEUS=true
```

> **Note**: Amadeus credentials not provided, running with `MockAmadeusClient` (MOCK BOOKINGS).

---

## Test Data

### Employees (artifacts/employees.json)
```json
{
  "employees": [
    { "employee_ref": "EMP001", "name": "Mohammed Alansari", "email": "moh.alansari2005@gmail.com" },
    { "employee_ref": "EMP002", "name": "Majara Contact", "email": "m.alansari@majaracapital.com" },
    { "employee_ref": "EMP003", "name": "John Doe", "email": "john.doe@example.com" }
  ]
}
```

### Trip Requests (artifacts/trip_requests.json)
```json
{
  "trip_requests": [
    { "employee_ref": "EMP001", "city": "PAR", "check_in": "2026-03-01", "check_out": "2026-03-03", "max_nightly_budget": "220.00" },
    { "employee_ref": "EMP002", "city": "LON", "check_in": "2026-03-05", "check_out": "2026-03-08", "max_nightly_budget": "280.00" },
    { "employee_ref": "EMP003", "city": "PAR", "check_in": "2026-03-02", "check_out": "2026-03-06", "max_nightly_budget": "200.00" }
  ]
}
```

---

## Step-by-Step Commands

### Step 1: Upload Employees
```bash
curl -X POST http://localhost:8000/v1/bulk/employees \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d @artifacts/employees.json
```

**Response** (artifacts/resp_employees.json):
```json
{ "created": 3, "updated": 0, "skipped": 0, "errors": [] }
```

### Step 2: Upload Trip Requests
```bash
curl -X POST http://localhost:8000/v1/bulk/trip-requests \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d @artifacts/trip_requests.json
```

**Response** (artifacts/resp_trip_requests.json):
```json
{ "created": 3, "updated": 0, "skipped": 0, "errors": [] }
```

### Step 3: Run OPTIONS Job
```bash
curl -X POST http://localhost:8000/v1/bulk/options/run \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Job ID**: `ed397a06-593d-440e-ba6c-65e2e764de7e`

**Final Status** (artifacts/options_job_status.json):
```json
{
  "id": "ed397a06-593d-440e-ba6c-65e2e764de7e",
  "job_type": "OPTIONS",
  "status": "COMPLETED",
  "total_count": 3,
  "success_count": 3,
  "failed_count": 0
}
```

### Step 4: Run BOOK Job
```bash
curl -X POST http://localhost:8000/v1/bulk/book \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{
    "selection_strategy": "CHEAPEST",
    "email_notifications": true,
    "payment": { "type": "test", "token": "test-token" }
  }'
```

**Job ID**: `0f45f269-d0bf-4166-af64-61d40f13c3f6`

**Final Status** (artifacts/book_job_status.json):
```json
{
  "id": "0f45f269-d0bf-4166-af64-61d40f13c3f6",
  "job_type": "BOOK",
  "status": "COMPLETED",
  "total_count": 3,
  "success_count": 3,
  "failed_count": 0,
  "skipped_count": 0
}
```

---

## Hotel Options Results

### EMP001 - Mohammed Alansari (PAR, 2 nights)
**Trip Request ID**: `bbf46285-5cc7-437c-a3ee-c538d00edb4e`

| Rank | Hotel | Price/Night | Total | Currency | Offer ID |
|------|-------|-------------|-------|----------|----------|
| 1 | Mock Hotel PAR 1 | $144.00 | $288.00 | USD | OFFERPAR2026-03-01000 |
| 2 | Mock Hotel PAR 2 | $169.00 | $338.00 | USD | OFFERPAR2026-03-01001 |
| 3 | Mock Hotel PAR 3 | $194.00 | $388.00 | USD | OFFERPAR2026-03-01002 |
| 4 | Mock Hotel PAR 4 | $219.00 | $438.00 | USD | OFFERPAR2026-03-01003 |

### EMP002 - Majara Contact (LON, 3 nights)
**Trip Request ID**: `8f420447-255c-4918-9bca-3a4aaa712045`

| Rank | Hotel | Price/Night | Total | Currency | Offer ID |
|------|-------|-------------|-------|----------|----------|
| 1 | Mock Hotel LON 1 | $114.00 | $342.00 | USD | OFFERLON2026-03-05000 |
| 2 | Mock Hotel LON 2 | $139.00 | $417.00 | USD | OFFERLON2026-03-05001 |
| 3 | Mock Hotel LON 3 | $164.00 | $492.00 | USD | OFFERLON2026-03-05002 |
| 4 | Mock Hotel LON 4 | $189.00 | $567.00 | USD | OFFERLON2026-03-05003 |
| 5 | Mock Hotel LON 5 | $214.00 | $642.00 | USD | OFFERLON2026-03-05004 |

### EMP003 - John Doe (PAR, 4 nights)
**Trip Request ID**: `788d31a9-78f2-41bc-8fa2-d128f4436cb3`

| Rank | Hotel | Price/Night | Total | Currency | Offer ID |
|------|-------|-------------|-------|----------|----------|
| 1 | Mock Hotel PAR 1 | $144.00 | $576.00 | USD | OFFERPAR2026-03-02000 |
| 2 | Mock Hotel PAR 2 | $169.00 | $676.00 | USD | OFFERPAR2026-03-02001 |
| 3 | Mock Hotel PAR 3 | $194.00 | $776.00 | USD | OFFERPAR2026-03-02002 |

---

## Booking Results (MOCK BOOKINGS)

| Employee | City | Hotel | Dates | Total | Reference | Order ID | Status |
|----------|------|-------|-------|-------|-----------|----------|--------|
| Mohammed Alansari | PAR | Mock Hotel PAR 1 | Mar 1-3 | $288.00 | REF000001 | ORDER000001 | ✅ CONFIRMED |
| Majara Contact | LON | Mock Hotel LON 1 | Mar 5-8 | $342.00 | REF000002 | ORDER000002 | ✅ CONFIRMED |
| John Doe | PAR | Mock Hotel PAR 1 | Mar 2-6 | $576.00 | REF000003 | ORDER000003 | ✅ CONFIRMED |

**Selection Strategy**: CHEAPEST (rank 1 selected for all)

---

## Email Delivery Results

Emails sent via **Resend API** on 2026-01-07.

| Recipient | Subject | Status | Message ID | Timestamp |
|-----------|---------|--------|------------|-----------|
| moh.alansari2005@gmail.com | Hotel Booking Confirmed - Mock Hotel PAR 1 | ✅ DELIVERED | `791d0e51-27b4-4070-b959-9fc4e433502e` | 2026-01-07T17:11:32 |
| m.alansari@majaracapital.com | Hotel Booking Confirmed - Mock Hotel LON 1 | ⚠️ SKIPPED | - | - |
| john.doe@example.com | Hotel Booking Confirmed - Mock Hotel PAR 1 | ⚠️ SKIPPED | - | - |

> **Note**: Resend free tier only allows sending to your own verified email. To send to other recipients, verify a domain at resend.com/domains.

### Email Content Proof (for moh.alansari2005@gmail.com)
- **Subject**: Hotel Booking Confirmed - Mock Hotel PAR 1
- **Booking Reference in Body**: REF000001
- **Order ID in Body**: ORDER000001
- **Check-in**: 2026-03-01
- **Check-out**: 2026-03-03
- **Total Price**: USD 288.00

---

## Issues and Fixes

### Issue 1: Gmail SMTP Authentication Failed
**Error**: `535 5.7.8 Username and Password not accepted`  
**Cause**: Gmail requires App Password, not regular password  
**Fix**: Switched to Resend API for email delivery

### Issue 2: Celery Async/Sync Event Loop Error
**Error**: `RuntimeError: There is no current event loop in thread 'MainThread'`  
**Cause**: `asyncio.get_event_loop()` fails in Celery worker processes  
**Fix**: Added `run_async()` helper using `asyncio.run()` for proper event loop handling

### Issue 3: Resend Free Tier Limitation
**Error**: `You can only send testing emails to your own email address`  
**Cause**: Resend free tier restriction  
**Note**: 1/3 emails delivered successfully to verified email

---

## Artifacts Directory

```
artifacts/
├── employees.json              # Input: Employee data
├── trip_requests.json          # Input: Trip request data
├── resp_employees.json         # Response: Employee upload
├── resp_trip_requests.json     # Response: Trip request upload
├── options_job_start.json      # Response: OPTIONS job queued
├── options_job_status.json     # Response: OPTIONS job completed
├── options_bbf46285.json       # EMP001 hotel options
├── options_8f420447.json       # EMP002 hotel options
├── options_788d31a9.json       # EMP003 hotel options
├── book_job_start.json         # Response: BOOK job queued
├── book_job_status.json        # Response: BOOK job completed
├── book_results.json           # Full booking results
├── email_delivery_results.json # Resend API responses
└── send_emails.py              # Email sending script
```

---

## Summary

| Metric | Result |
|--------|--------|
| Employees Created | 3/3 ✅ |
| Trip Requests Created | 3/3 ✅ |
| Hotel Options Generated | 12 total (4+5+3) ✅ |
| Bookings Confirmed | 3/3 ✅ |
| Emails Delivered | 1/3 ⚠️ (Resend free tier limit) |
| Total Booking Value | $1,206.00 USD |

**Test Status**: ✅ PASSED (with noted email limitation)
