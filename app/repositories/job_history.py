from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.job_history import JobHistory
from app.repositories.base import BaseRepository


class JobHistoryRepository(BaseRepository[JobHistory]):
    def __init__(self) -> None:
        super().__init__(JobHistory)

    def list_items(self, db: Session, job_type: str | None = None, status: str | None = None, offset: int = 0, limit: int = 100) -> list[JobHistory]:
        query = db.query(JobHistory)
        if job_type is not None:
            query = query.filter(JobHistory.job_type == job_type)
        if status is not None:
            query = query.filter(JobHistory.status == status)
        return query.order_by(JobHistory.started_at.desc()).offset(offset).limit(limit).all()

    def count_by_status(self, db: Session, job_types: list) -> dict:
        rows = (
            db.query(JobHistory.status, func.count(JobHistory.id))
            .filter(JobHistory.job_type.in_(job_types))
            .group_by(JobHistory.status)
            .all()
        )
        return dict(rows)

    def list_by_status(self, db: Session, status: str, offset: int = 0, limit: int = 100) -> list[JobHistory]:
        return db.query(JobHistory).filter(JobHistory.status == status).offset(offset).limit(limit).all()

    def get_by_task_id(self, db: Session, task_id: str) -> JobHistory | None:
        return db.query(JobHistory).filter(JobHistory.task_id == task_id).one_or_none()
