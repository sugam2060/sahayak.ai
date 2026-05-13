from celery import Celery
from shared.config import REDIS_URL

# Create Celery instance
celery_app = Celery(
    "sahayak_tasks",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["shared.mail_service"]
)

# Optional configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
