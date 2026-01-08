"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_bulk import router as bulk_router
from app.api.routes_jobs import router as jobs_router
from app.api.routes_trip_requests import router as trip_requests_router
from app.core.config import get_settings
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    setup_logging()
    yield
    # Shutdown


settings = get_settings()

app = FastAPI(
    title="Keyraa Hotel Booking API",
    description="Corporate hotel booking API with Amadeus integration",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(bulk_router)
app.include_router(jobs_router)
app.include_router(trip_requests_router)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": "Keyraa Hotel Booking API",
        "version": "1.0.0",
        "docs": "/docs",
    }
