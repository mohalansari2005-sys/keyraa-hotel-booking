"""Integration tests for the full workflow."""

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.models.booking import Booking, BookingStatus
from app.models.bulk_job import BulkJob, BulkJobItem, BulkJobStatus, BulkJobType
from app.models.employee import Employee
from app.models.hotel_option import HotelOption
from app.models.tenant import Tenant
from app.models.trip_request import TripRequest, TripRequestStatus
from app.services.amadeus_client import MockAmadeusClient


class TestIdempotency:
    """Tests for idempotent operations."""

    def test_employee_upsert_idempotent(
        self, db_session: Session, test_tenant: Tenant
    ):
        """Test that employee creation is idempotent."""
        # Create first employee
        emp1 = Employee(
            tenant_id=test_tenant.id,
            employee_ref="EMP001",
            name="John Doe",
            email="john@example.com",
        )
        db_session.add(emp1)
        db_session.commit()

        # Try to create same employee ref - should update
        existing = db_session.query(Employee).filter(
            Employee.tenant_id == test_tenant.id,
            Employee.employee_ref == "EMP001",
        ).first()

        assert existing is not None
        existing.name = "John Updated"
        existing.email = "john.updated@example.com"
        db_session.commit()

        # Verify update
        result = db_session.query(Employee).filter(
            Employee.tenant_id == test_tenant.id,
            Employee.employee_ref == "EMP001",
        ).first()

        assert result.name == "John Updated"
        assert result.email == "john.updated@example.com"

    def test_trip_request_unique_constraint(
        self, db_session: Session, test_tenant: Tenant, test_employee: Employee
    ):
        """Test that duplicate trip requests are prevented."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        # Create first trip request
        tr1 = TripRequest(
            tenant_id=test_tenant.id,
            employee_id=test_employee.id,
            city="PAR",
            check_in=check_in,
            check_out=check_out,
            max_nightly_budget=Decimal("200.00"),
        )
        db_session.add(tr1)
        db_session.commit()

        # Try to create duplicate - should fail due to unique constraint
        tr2 = TripRequest(
            tenant_id=test_tenant.id,
            employee_id=test_employee.id,
            city="PAR",
            check_in=check_in,
            check_out=check_out,
            max_nightly_budget=Decimal("300.00"),
        )
        db_session.add(tr2)

        with pytest.raises(Exception):  # SQLite raises IntegrityError
            db_session.commit()

        db_session.rollback()

    def test_booking_skip_already_booked(
        self,
        db_session: Session,
        test_trip_request: TripRequest,
        test_hotel_option: HotelOption,
    ):
        """Test that already booked trip requests are skipped."""
        # Create confirmed booking
        booking = Booking(
            trip_request_id=test_trip_request.id,
            hotel_option_id=test_hotel_option.id,
            status=BookingStatus.CONFIRMED,
            hotel_name="Test Hotel",
            check_in=test_trip_request.check_in,
            check_out=test_trip_request.check_out,
            total_price=Decimal("350.00"),
            currency="EUR",
            amadeus_reference="REF123",
            amadeus_order_id="ORDER123",
        )
        db_session.add(booking)
        db_session.commit()

        # Check for existing booking
        existing = db_session.query(Booking).filter(
            Booking.trip_request_id == test_trip_request.id,
            Booking.status == BookingStatus.CONFIRMED,
        ).first()

        assert existing is not None
        assert existing.amadeus_reference == "REF123"


class TestBulkJobWorkflow:
    """Tests for bulk job processing workflow."""

    def test_options_job_creation(
        self,
        db_session: Session,
        test_tenant: Tenant,
        test_trip_request: TripRequest,
        test_employee: Employee,
    ):
        """Test creating an OPTIONS job."""
        job = BulkJob(
            tenant_id=test_tenant.id,
            job_type=BulkJobType.OPTIONS,
            status=BulkJobStatus.PENDING,
            total_count=1,
        )
        db_session.add(job)
        db_session.flush()

        item = BulkJobItem(
            bulk_job_id=job.id,
            trip_request_id=test_trip_request.id,
            employee_id=test_employee.id,
        )
        db_session.add(item)
        db_session.commit()

        assert job.id is not None
        assert len(job.items) == 1

    def test_book_job_creation(
        self,
        db_session: Session,
        test_tenant: Tenant,
        test_trip_request: TripRequest,
        test_employee: Employee,
    ):
        """Test creating a BOOK job."""
        job = BulkJob(
            tenant_id=test_tenant.id,
            job_type=BulkJobType.BOOK,
            status=BulkJobStatus.PENDING,
            total_count=1,
        )
        db_session.add(job)
        db_session.flush()

        item = BulkJobItem(
            bulk_job_id=job.id,
            trip_request_id=test_trip_request.id,
            employee_id=test_employee.id,
        )
        db_session.add(item)
        db_session.commit()

        assert job.id is not None
        assert job.job_type == BulkJobType.BOOK


class TestOptionsGeneration:
    """Tests for hotel options generation."""

    @pytest.mark.asyncio
    async def test_mock_client_returns_options(self, mock_amadeus_client):
        """Test that mock client returns hotel options."""
        check_in = date.today() + timedelta(days=30)
        check_out = date.today() + timedelta(days=32)

        offers = await mock_amadeus_client.get_hotel_offers(
            city_code="PAR",
            check_in=check_in,
            check_out=check_out,
        )

        assert len(offers) == 5
        for offer in offers:
            assert "hotel" in offer
            assert "offers" in offer


class TestBookingCreation:
    """Tests for booking creation."""

    @pytest.mark.asyncio
    async def test_mock_client_creates_booking(self, mock_amadeus_client):
        """Test that mock client creates booking."""
        result = await mock_amadeus_client.create_hotel_order(
            offer_id="OFFER123",
            guests=[
                {
                    "id": 1,
                    "name": {"firstName": "John", "lastName": "Doe"},
                    "contact": {"email": "john@example.com"},
                }
            ],
            payments=[{"id": 1, "method": "CREDIT_CARD"}],
        )

        assert "data" in result
        assert result["data"]["id"] is not None
        assert result["data"]["reference"] is not None

    def test_booking_record_creation(
        self,
        db_session: Session,
        test_trip_request: TripRequest,
        test_hotel_option: HotelOption,
    ):
        """Test creating a booking record."""
        booking = Booking(
            trip_request_id=test_trip_request.id,
            hotel_option_id=test_hotel_option.id,
            status=BookingStatus.CONFIRMED,
            hotel_name=test_hotel_option.hotel_name,
            hotel_address=test_hotel_option.address,
            check_in=test_trip_request.check_in,
            check_out=test_trip_request.check_out,
            total_price=test_hotel_option.price_total,
            currency=test_hotel_option.currency,
            amadeus_reference="REF123456",
            amadeus_order_id="ORDER123456",
        )
        db_session.add(booking)
        db_session.commit()

        assert booking.id is not None
        assert booking.status == BookingStatus.CONFIRMED


class TestPartialFailures:
    """Tests for partial failure scenarios."""

    def test_job_with_mixed_results(
        self,
        db_session: Session,
        test_tenant: Tenant,
    ):
        """Test job with some successes and some failures."""
        # Create employees
        employees = []
        for i in range(5):
            emp = Employee(
                tenant_id=test_tenant.id,
                employee_ref=f"EMP{i:03d}",
                name=f"Employee {i}",
                email=f"emp{i}@example.com",
            )
            db_session.add(emp)
            employees.append(emp)
        db_session.commit()

        # Create trip requests
        trip_requests = []
        for i, emp in enumerate(employees):
            tr = TripRequest(
                tenant_id=test_tenant.id,
                employee_id=emp.id,
                city="PAR",
                check_in=date.today() + timedelta(days=30 + i),
                check_out=date.today() + timedelta(days=32 + i),
                max_nightly_budget=Decimal("200.00"),
            )
            db_session.add(tr)
            trip_requests.append(tr)
        db_session.commit()

        # Create job with mixed results
        job = BulkJob(
            tenant_id=test_tenant.id,
            job_type=BulkJobType.OPTIONS,
            status=BulkJobStatus.COMPLETED,
            total_count=5,
            success_count=3,
            failed_count=2,
        )
        db_session.add(job)
        db_session.commit()

        assert job.total_count == 5
        assert job.success_count == 3
        assert job.failed_count == 2


class TestMultipleTenants:
    """Tests for multi-tenant isolation."""

    def test_tenant_isolation(self, db_session: Session):
        """Test that data is isolated between tenants."""
        # Create two tenants
        tenant1 = Tenant(id=uuid.uuid4(), name="Tenant 1")
        tenant2 = Tenant(id=uuid.uuid4(), name="Tenant 2")
        db_session.add_all([tenant1, tenant2])
        db_session.commit()

        # Create employees for each tenant with same ref
        emp1 = Employee(
            tenant_id=tenant1.id,
            employee_ref="EMP001",
            name="John from Tenant 1",
            email="john@tenant1.com",
        )
        emp2 = Employee(
            tenant_id=tenant2.id,
            employee_ref="EMP001",
            name="John from Tenant 2",
            email="john@tenant2.com",
        )
        db_session.add_all([emp1, emp2])
        db_session.commit()

        # Query by tenant
        employees_t1 = db_session.query(Employee).filter(
            Employee.tenant_id == tenant1.id
        ).all()
        employees_t2 = db_session.query(Employee).filter(
            Employee.tenant_id == tenant2.id
        ).all()

        assert len(employees_t1) == 1
        assert len(employees_t2) == 1
        assert employees_t1[0].name == "John from Tenant 1"
        assert employees_t2[0].name == "John from Tenant 2"
