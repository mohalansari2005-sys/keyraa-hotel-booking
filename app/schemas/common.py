"""Common schemas and base classes."""

from typing import Any, Generic, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True,
    )


T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    page: int = 1
    page_size: int = 50


class BulkSummary(BaseModel):
    """Summary response for bulk operations."""

    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: list[dict[str, Any]] = []


class JobResponse(BaseModel):
    """Response for async job creation."""

    job_id: UUID
    status: str = "PENDING"
    message: str = "Job queued for processing"


class ErrorResponse(BaseModel):
    """Standard error response."""

    error: str
    detail: str | None = None
    code: str | None = None
