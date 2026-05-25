from sqlalchemy.orm import Session

from app.models.screenshot import Screenshot
from app.repositories.base import BaseRepository


class ScreenshotRepository(BaseRepository[Screenshot]):
    def __init__(self) -> None:
        super().__init__(Screenshot)

    def get(self, db: Session, id: str) -> Screenshot | None:
        return super().get(db, id)

    def list_by_entry(self, db: Session, archive_entry_id: str) -> list[Screenshot]:
        return db.query(Screenshot).filter(Screenshot.archive_entry_id == archive_entry_id).all()
