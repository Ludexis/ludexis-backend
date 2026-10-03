from app.db.session import SessionLocal
from app.tasks.celery_app import celery_app


@celery_app.task
def scheduler_tick_task() -> list[str]:
    from app.services.scheduler import SchedulerService

    db = SessionLocal()
    try:
        return SchedulerService().tick(db)
    finally:
        db.close()
