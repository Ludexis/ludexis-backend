from celery import Celery
from celery.schedules import crontab
from celery.signals import setup_logging

from app.core.config import settings
from app.core.logging import setup_logging as configure_logging

#configure_logging()

#@setup_logging.connect
#def configure_celery_logging(*args, **kwargs):
#    configure_logging()

celery_app = Celery(
    "ludexis",
    broker=str(settings.CELERY_BROKER_URL),
    backend=str(settings.CELERY_RESULT_BACKEND),
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,
)


import app.tasks.scan_tasks  # noqa: F401
import app.tasks.artwork_tasks  # noqa: F401
import app.tasks.metadata_tasks  # noqa: F401
import app.tasks.scheduler_tasks  # noqa: F401


celery_app.conf.beat_schedule = {
    # Schedules live in the scheduled_tasks table and are edited from the admin UI; the tick starts due ones.
    "scheduler-tick": {
        "task": "app.tasks.scheduler_tasks.scheduler_tick_task",
        "schedule": crontab(minute="*/5"),
    },
}

