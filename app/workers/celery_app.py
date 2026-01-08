"""Celery application configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "keyraa",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Concurrency settings - limit parallel Amadeus calls
    worker_concurrency=4,
    worker_prefetch_multiplier=1,
    
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Result settings
    result_expires=3600,  # 1 hour
    
    # Retry settings
    task_default_retry_delay=5,
    task_max_retries=3,
)

# Task routing disabled for POC - using default queue
# For production, enable these and run workers with: celery -A app.workers.celery_app worker -Q options,bookings
# celery_app.conf.task_routes = {
#     "app.workers.tasks.generate_options_job": {"queue": "options"},
#     "app.workers.tasks.book_bulk_job": {"queue": "bookings"},
# }
