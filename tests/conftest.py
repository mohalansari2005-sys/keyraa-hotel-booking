"""Pytest fixtures and configuration."""

import asyncio
import os
import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import AsyncGenerator, Generator
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Set test environment before importing app modules
os.environ["DATABASE_URL"] = "postgresql+asyncpg://test:test@localhost:5432/test"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///:memory:"
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_BROKER_URL"] = "redis://localhost:6379/0"
os.environ["CELERY_RESULT_BACKEND"] = "redis://localhost:6379/0"
os.environ["AMADEUS_CLIENT_ID"] = "test_client_id"
os.environ["AMADEUS_CLIENT_SECRET"] = "test_client_secret"
os.environ["SMTP_HOST"] = "localhost"
os.environ["SMTP_PORT"] = "1025"

from app.api.deps import get_db, get_tenant_id
from app.core.db import async_session_factory
from app.main import app
from app.models.base import Base
from app.models.booking import Booking, BookingStatus
from app.models.bulk_job import BulkJob, BulkJobItem, BulkJobStatus, BulkJobType
from app.models.employee import Employee
from app.models.hotel_option import HotelOption
from app.models.tenant import Tenant
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.amadeus_client import MockAmadeusClient


# Test database setup (SQLite for unit tests)
TEST_DATABASE_URL = "sqlite:///:memory:"

test_engine = create_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=test_engine,
)


# Enable foreign keys for SQLite
@event.listens_for(test_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=test_engine)
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=test_engine)


@pytest.fixture(scope="function")
def test_tenant(db_session: Session) -> Tenant:
    """Create a test tenant."""
    tenant = Tenant(
        id=uuid.uuid4(),
        name="Test Tenant",
    )
    db_session.add(tenant)
    db_session.commit()
    return tenant


@pytest.fixture(scope="function")
def test_employee(db_session: Session, test_tenant: Tenant) -> Employee:
    """Create a test employee."""
    employee = Employee(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        employee_ref="EMP001",
        name="John Doe",
        email="john@example.com",
    )
    db_session.add(employee)
    db_session.commit()
    return employee


@pytest.fixture(scope="function")
def test_trip_request(
    db_session: Session, test_tenant: Tenant, test_employee: Employee
) -> TripRequest:
    """Create a test trip request."""
    trip_request = TripRequest(
        id=uuid.uuid4(),
        tenant_id=test_tenant.id,
        employee_id=test_employee.id,
        city="PAR",
        check_in=date.today() + timedelta(days=30),
        check_out=date.today() + timedelta(days=32),
        max_nightly_budget=Decimal("200.00"),
        status=TripRequestStatus.PENDING,
    )
    db_session.add(trip_request)
    db_session.commit()
    return trip_request


@pytest.fixture(scope="function")
def test_hotel_option(
    db_session: Session, test_trip_request: TripRequest
) -> HotelOption:
    """Create a test hotel option."""
    option = HotelOption(
        id=uuid.uuid4(),
        trip_request_id=test_trip_request.id,
        provider="amadeus",
        hotel_id="MOCKPAR001",
        offer_id="OFFER123",
        hotel_name="Test Hotel Paris",
        address="123 Test Street, Paris",
        price_total=Decimal("350.00"),
        price_per_night=Decimal("175.00"),
        currency="EUR",
        rank=1,
    )
    db_session.add(option)
    db_session.commit()
    return option


@pytest.fixture(scope="function")
def mock_amadeus_client() -> MockAmadeusClient:
    """Create a mock Amadeus client."""
    return MockAmadeusClient()


@pytest.fixture(scope="function")
def mock_amadeus_client_no_offers() -> MockAmadeusClient:
    """Create a mock Amadeus client that returns no offers."""
    return MockAmadeusClient(no_offers=True)


@pytest.fixture(scope="function")
def mock_amadeus_client_fail_booking() -> MockAmadeusClient:
    """Create a mock Amadeus client that fails bookings."""
    return MockAmadeusClient(fail_booking=True)


# FastAPI test client fixtures
@pytest.fixture(scope="function")
def client(db_session: Session, test_tenant: Tenant) -> Generator[TestClient, None, None]:
    """Create a test client with overridden dependencies."""
    
    # Create a mock async session that wraps our sync session
    async def override_get_db():
        # For testing, we'll use a mock that proxies to sync session
        yield db_session
    
    async def override_get_tenant_id():
        return test_tenant.id
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_tenant_id] = lambda: test_tenant.id
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_employees_json() -> list[dict]:
    """Sample employee data for bulk upload."""
    return [
        {"employee_ref": "EMP001", "name": "John Doe", "email": "john@example.com"},
        {"employee_ref": "EMP002", "name": "Jane Smith", "email": "jane@example.com"},
        {"employee_ref": "EMP003", "name": "Bob Wilson", "email": "bob@example.com"},
    ]


@pytest.fixture
def sample_trip_requests_json() -> list[dict]:
    """Sample trip request data for bulk upload."""
    check_in = (date.today() + timedelta(days=30)).isoformat()
    check_out = (date.today() + timedelta(days=32)).isoformat()
    return [
        {
            "employee_ref": "EMP001",
            "city": "PAR",
            "check_in": check_in,
            "check_out": check_out,
            "max_nightly_budget": "200.00",
        },
        {
            "employee_ref": "EMP002",
            "city": "LON",
            "check_in": check_in,
            "check_out": check_out,
            "max_nightly_budget": "250.00",
        },
    ]


@pytest.fixture
def sample_csv_employees() -> str:
    """Sample CSV content for employee upload."""
    return """employee_ref,name,email
EMP001,John Doe,john@example.com
EMP002,Jane Smith,jane@example.com
EMP003,Bob Wilson,bob@example.com
"""


@pytest.fixture
def sample_csv_trip_requests() -> str:
    """Sample CSV content for trip request upload."""
    check_in = (date.today() + timedelta(days=30)).isoformat()
    check_out = (date.today() + timedelta(days=32)).isoformat()
    return f"""employee_ref,city,check_in,check_out,max_nightly_budget
EMP001,PAR,{check_in},{check_out},200.00
EMP002,LON,{check_in},{check_out},250.00
"""
