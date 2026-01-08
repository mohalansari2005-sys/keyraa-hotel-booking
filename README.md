# Keyraa Hotel Booking Backend PoC

A FastAPI backend for corporate hotel bookings with Amadeus Self-Service API integration, bulk processing via Celery, and email notifications.

## Features

- **Bulk Operations**: Upload employees and trip requests via JSON or CSV
- **Hotel Search**: Automated hotel options generation via Amadeus API
- **Bulk Booking**: Book multiple hotels in one operation
- **Email Notifications**: Automatic confirmation/failure emails via SMTP
- **Multi-tenancy**: Tenant isolation via `X-Tenant-Id` header
- **Async Processing**: Background job processing with Celery + Redis
- **Idempotency**: Safe retry handling for all operations

## Tech Stack

- **Framework**: FastAPI + Pydantic v2
- **Database**: PostgreSQL + SQLAlchemy 2.0 + Alembic
- **Task Queue**: Celery + Redis
- **Email**: SMTP (Mailhog for local development)
- **External API**: Amadeus Self-Service APIs

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) Amadeus API credentials from [Amadeus for Developers](https://developers.amadeus.com/)

### 1. Clone and Setup

```bash
cd "Keyraa poc"

# Copy environment file
cp .env.example .env

# (Optional) Add your Amadeus credentials to .env
# AMADEUS_CLIENT_ID=your_client_id
# AMADEUS_CLIENT_SECRET=your_client_secret
```

### 2. Start Services

```bash
# Start all services (postgres, redis, mailhog, api, worker)
docker-compose up -d

# Run database migrations
docker-compose run --rm migrate

# Check logs
docker-compose logs -f api worker
```

### 3. Access Services

| Service | URL |
|---------|-----|
| API | http://localhost:8000 |
| API Docs | http://localhost:8000/docs |
| Mailhog UI | http://localhost:8025 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

## API Usage

### Step 1: Upload Employees

```bash
# JSON format
curl -X POST http://localhost:8000/v1/bulk/employees \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{
    "employees": [
      {"employee_ref": "EMP001", "name": "John Doe", "email": "john@example.com"},
      {"employee_ref": "EMP002", "name": "Jane Smith", "email": "jane@example.com"},
      {"employee_ref": "EMP003", "name": "Bob Wilson", "email": "bob@example.com"}
    ]
  }'
```

### Step 2: Upload Trip Requests

```bash
curl -X POST http://localhost:8000/v1/bulk/trip-requests \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{
    "trip_requests": [
      {"employee_ref": "EMP001", "city": "PAR", "check_in": "2026-03-01", "check_out": "2026-03-03", "max_nightly_budget": "200.00"},
      {"employee_ref": "EMP002", "city": "LON", "check_in": "2026-03-05", "check_out": "2026-03-07", "max_nightly_budget": "250.00"}
    ]
  }'
```

### Step 3: Generate Hotel Options

```bash
# Start OPTIONS job
curl -X POST http://localhost:8000/v1/bulk/options/run \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{}'

# Response: {"job_id": "...", "status": "PENDING", "message": "..."}
```

### Step 4: Check Job Status

```bash
curl http://localhost:8000/v1/bulk/jobs/{job_id} \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111"

# Response: {"id": "...", "status": "COMPLETED", "success_count": 2, ...}
```

### Step 5: View Options for a Trip Request

```bash
curl http://localhost:8000/v1/trip-requests/{trip_request_id}/options \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111"

# Response: {"trip_request_id": "...", "options": [...]}
```

### Step 6: Bulk Booking

```bash
curl -X POST http://localhost:8000/v1/bulk/book \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -H "Content-Type: application/json" \
  -d '{
    "selection_strategy": "CHEAPEST",
    "email_notifications": true,
    "payment": {
      "type": "test",
      "token": "test-token"
    }
  }'

# Response: {"job_id": "...", "status": "PENDING", ...}
```

### Step 7: Check Booking Results

```bash
curl http://localhost:8000/v1/bulk/jobs/{book_job_id}/results \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111"

# Response includes per-employee results with booking references
```

### Step 8: Check Emails

Open http://localhost:8025 to see booking confirmation emails in Mailhog.

## CSV Upload Format

### employees.csv

```csv
employee_ref,name,email
EMP001,John Doe,john@example.com
EMP002,Jane Smith,jane@example.com
EMP003,Bob Wilson,bob@example.com
```

### trip_requests.csv

```csv
employee_ref,city,check_in,check_out,max_nightly_budget
EMP001,PAR,2026-03-01,2026-03-03,200.00
EMP002,LON,2026-03-05,2026-03-07,250.00
```

### Upload CSV

```bash
curl -X POST http://localhost:8000/v1/bulk/employees \
  -H "X-Tenant-Id: 11111111-1111-1111-1111-111111111111" \
  -F "file=@employees.csv"
```

## Running Tests

```bash
# Install dependencies locally (for test development)
pip install -r requirements.txt

# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=app --cov-report=term-missing

# Run specific test file
pytest tests/test_schemas.py -v
```

## Project Structure

```
app/
├── main.py                    # FastAPI application
├── api/
│   ├── deps.py                # Dependencies (DB, tenant header)
│   ├── routes_bulk.py         # Bulk upload endpoints
│   ├── routes_jobs.py         # Job status endpoints
│   └── routes_trip_requests.py # Trip request endpoints
├── core/
│   ├── config.py              # Settings from environment
│   ├── db.py                  # SQLAlchemy configuration
│   └── logging.py             # Logging utilities
├── models/                    # SQLAlchemy models
├── schemas/                   # Pydantic schemas
├── services/
│   ├── amadeus_client.py      # Amadeus API client
│   ├── booking_service.py     # Booking logic
│   ├── option_service.py      # Hotel option handling
│   └── email_service.py       # Email sending
└── workers/
    ├── celery_app.py          # Celery configuration
    └── tasks.py               # Background tasks
```

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection (async) | Required |
| `DATABASE_URL_SYNC` | PostgreSQL connection (sync) | Required |
| `REDIS_URL` | Redis connection | `redis://localhost:6379/0` |
| `AMADEUS_CLIENT_ID` | Amadeus API client ID | - |
| `AMADEUS_CLIENT_SECRET` | Amadeus API client secret | - |
| `SMTP_HOST` | SMTP server host | `localhost` |
| `SMTP_PORT` | SMTP server port | `1025` |
| `EMAIL_FROM` | From email address | `bookings@keyraa.local` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Development

### Local Development (without Docker)

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start PostgreSQL and Redis (your local instances)
# Update .env with connection details

# Run migrations
alembic upgrade head

# Start API server
uvicorn app.main:app --reload

# In another terminal, start Celery worker
celery -A app.workers.celery_app worker --loglevel=info
```

### Creating New Migrations

```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

## Architecture Notes

### Token Caching
- Amadeus OAuth2 tokens cached in memory with 60-second buffer before expiry
- Thread-safe implementation using Python's `threading.Lock`

### Retry Policy
- HTTP 429/5xx: Exponential backoff (1s, 2s, 4s), max 3 attempts
- HTTP 401: Token refresh and single retry

### Idempotency
- Employees: Unique on `(tenant_id, employee_ref)`
- Trip Requests: Unique on `(tenant_id, employee_id, city, check_in, check_out)`
- Bookings: Skip if `CONFIRMED` booking exists for trip request

### Concurrency Limits
- Celery worker: 4 concurrent tasks
- Prevents Amadeus API rate limiting

### Security
- Payment data passed to Amadeus but never logged or stored
- Sensitive fields redacted in logs via `safe_log_dict()`

## License

MIT License
