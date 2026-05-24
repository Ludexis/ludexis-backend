import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.repositories.base import BaseRepository


class ArchiveEntryRepository(BaseRepository[ArchiveEntry]):
    def __init__(self) -> None:
        super().__init__(ArchiveEntry)

    def list_active(self, db: Session, offset: int = 0, limit: int = 100) -> list[ArchiveEntry]:
        return (
            db.query(ArchiveEntry)
            .filter(ArchiveEntry.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_active(self, db: Session, id: str) -> ArchiveEntry | None:
        return db.query(ArchiveEntry).filter(ArchiveEntry.id == id, ArchiveEntry.deleted_at.is_(None)).one_or_none()

    def search(self, db: Session, query: str, offset: int = 0, limit: int = 100) -> list[ArchiveEntry]:
        q = select(ArchiveEntry).where(
            ArchiveEntry.deleted_at.is_(None),
            sa.or_(
                ArchiveEntry.title.ilike(f"%{query}%"),
                ArchiveEntry.description.ilike(f"%{query}%"),
            ),
        ).offset(offset).limit(limit)
        return db.execute(q).scalars().all()
