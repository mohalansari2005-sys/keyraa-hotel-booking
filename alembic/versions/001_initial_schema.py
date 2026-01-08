"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2026-01-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create tenants table
    op.create_table(
        'tenants',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create employees table
    op.create_table(
        'employees',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_ref', sa.String(100), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'employee_ref', name='uq_employee_ref')
    )
    op.create_index('ix_employees_tenant_id', 'employees', ['tenant_id'])

    # Create trip_requests table
    op.create_table(
        'trip_requests',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('city', sa.String(100), nullable=False),
        sa.Column('check_in', sa.Date(), nullable=False),
        sa.Column('check_out', sa.Date(), nullable=False),
        sa.Column('max_nightly_budget', sa.Numeric(10, 2), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'employee_id', 'check_in', 'check_out', 'city', name='uq_trip_request')
    )
    op.create_index('ix_trip_requests_tenant_id', 'trip_requests', ['tenant_id'])
    op.create_index('ix_trip_requests_employee_id', 'trip_requests', ['employee_id'])
    op.create_index('ix_trip_request_status', 'trip_requests', ['status'])

    # Create hotel_options table
    op.create_table(
        'hotel_options',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trip_request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider', sa.String(50), nullable=False, server_default='amadeus'),
        sa.Column('hotel_id', sa.String(100), nullable=False),
        sa.Column('offer_id', sa.String(255), nullable=False),
        sa.Column('hotel_name', sa.String(255), nullable=False),
        sa.Column('address', sa.Text(), nullable=True),
        sa.Column('price_total', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_per_night', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('payload_json', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['trip_request_id'], ['trip_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_hotel_options_trip_request_id', 'hotel_options', ['trip_request_id'])

    # Create bookings table
    op.create_table(
        'bookings',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trip_request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('hotel_option_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('provider', sa.String(50), nullable=False, server_default='amadeus'),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('amadeus_order_id', sa.String(255), nullable=True),
        sa.Column('amadeus_reference', sa.String(255), nullable=True),
        sa.Column('hotel_name', sa.String(255), nullable=False),
        sa.Column('hotel_address', sa.Text(), nullable=True),
        sa.Column('check_in', sa.Date(), nullable=False),
        sa.Column('check_out', sa.Date(), nullable=False),
        sa.Column('total_price', sa.Numeric(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), nullable=False),
        sa.Column('raw_response_json', postgresql.JSON(), nullable=True),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('email_sent', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['hotel_option_id'], ['hotel_options.id'], ),
        sa.ForeignKeyConstraint(['trip_request_id'], ['trip_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bookings_trip_request_id', 'bookings', ['trip_request_id'])

    # Create bulk_jobs table
    op.create_table(
        'bulk_jobs',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('job_type', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('total_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('success_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('failed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('skipped_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bulk_jobs_tenant_id', 'bulk_jobs', ['tenant_id'])

    # Create bulk_job_items table
    op.create_table(
        'bulk_job_items',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('bulk_job_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('trip_request_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('employee_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='PENDING'),
        sa.Column('error_code', sa.String(50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('booking_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('options_count', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
        sa.ForeignKeyConstraint(['bulk_job_id'], ['bulk_jobs.id'], ),
        sa.ForeignKeyConstraint(['employee_id'], ['employees.id'], ),
        sa.ForeignKeyConstraint(['trip_request_id'], ['trip_requests.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_bulk_job_items_bulk_job_id', 'bulk_job_items', ['bulk_job_id'])
    op.create_index('ix_bulk_job_items_trip_request_id', 'bulk_job_items', ['trip_request_id'])
    op.create_index('ix_bulk_job_items_employee_id', 'bulk_job_items', ['employee_id'])


def downgrade() -> None:
    op.drop_table('bulk_job_items')
    op.drop_table('bulk_jobs')
    op.drop_table('bookings')
    op.drop_table('hotel_options')
    op.drop_table('trip_requests')
    op.drop_table('employees')
    op.drop_table('tenants')
