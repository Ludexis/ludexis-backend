from sqlalchemy.orm import Session

from app.models.job_history import JobHistory
from app.repositories.base import BaseRepository


class JobHistoryRepository(BaseRepository[JobHistory]):
    def __init__(self) -> None:
        super().__init__(JobHistory)

    def list_by_status(self, db: Session, status: str, offset: int = 0, limit: int = 100) -> list[JobHistory]:
        return db.query(JobHistory).filter(JobHistory.status == status).offset(offset).limit(limit).all()
