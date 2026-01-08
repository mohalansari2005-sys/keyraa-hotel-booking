"""Employee schemas."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import BaseSchema


class EmployeeCreate(BaseModel):
    """Schema for creating an employee."""

    employee_ref: str = Field(..., min_length=1, max_length=100)
    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr


class EmployeeBulkCreate(BaseModel):
    """Schema for bulk employee upload (list)."""

    employees: list[EmployeeCreate]


class EmployeeResponse(BaseSchema):
    """Schema for employee response."""

    id: UUID
    tenant_id: UUID
    employee_ref: str
    name: str
    email: str
    created_at: datetime
    updated_at: datetime


class EmployeeBrief(BaseSchema):
    """Brief employee info for job results."""

    id: UUID
    employee_ref: str
    name: str
    email: str
