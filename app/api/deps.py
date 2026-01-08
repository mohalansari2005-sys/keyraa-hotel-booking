"""API dependencies."""

from collections.abc import AsyncGenerator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import async_session_factory
from app.models.tenant import Tenant


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting database sessions."""
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()


async def get_tenant_id(
    x_tenant_id: Annotated[str, Header()] = None,
) -> UUID:
    """
    Dependency for getting tenant ID from header.
    
    For POC, we accept any tenant ID and auto-create if needed.
    In production, this would validate against actual tenant records.
    """
    if not x_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id header is required",
        )

    try:
        return UUID(x_tenant_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="X-Tenant-Id must be a valid UUID",
        )


async def ensure_tenant_exists(
    db: AsyncSession,
    tenant_id: UUID,
) -> Tenant:
    """Ensure tenant exists, create if not (POC only)."""
    from sqlalchemy import select
    
    result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = result.scalar_one_or_none()

    if not tenant:
        # Auto-create tenant for POC
        tenant = Tenant(id=tenant_id, name=f"Tenant-{str(tenant_id)[:8]}")
        db.add(tenant)
        await db.commit()
        await db.refresh(tenant)

    return tenant


# Type aliases for dependencies
DBSession = Annotated[AsyncSession, Depends(get_db)]
TenantId = Annotated[UUID, Depends(get_tenant_id)]
