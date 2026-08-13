"""Celery application configuration."""
from celery import Celery
from app.config import settings

# Initialize Celery app
# Note: docker-compose uses app.workers.celery_app
celery_app = Celery(
    "modernization_platform",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["app.workers.migration_tasks"]
)

# Optional configuration overrides
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
