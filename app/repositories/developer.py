import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_developers
from app.models.developer import Developer
from app.repositories.base import BaseRepository


class DeveloperRepository(BaseRepository[Developer]):
    def __init__(self) -> None:
        super().__init__(Developer)

    def get_by_name(self, db: Session, name: str) -> Developer | None:
        return db.query(Developer).filter(Developer.name == name).one_or_none()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Developer]:
        query = db.query(Developer)
        if q:
            query = query.filter(Developer.name.ilike(f"%{q}%"))
        return query.order_by(Developer.name).offset(offset).limit(limit).all()

    def count(self, db: Session, q: str | None = None) -> int:
        query = db.query(sa.func.count(Developer.id))
        if q:
            query = query.filter(Developer.name.ilike(f"%{q}%"))
        return query.scalar()

    def count_entries_for_ids(self, db: Session, developer_ids: list[str]) -> dict[str, int]:
        if not developer_ids:
            return {}
        rows = (
            db.query(archive_entry_developers.c.developer_id, sa.func.count(archive_entry_developers.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_developers.c.archive_entry_id)
            .filter(archive_entry_developers.c.developer_id.in_(developer_ids), ArchiveEntry.deleted_at.is_(None))
            .group_by(archive_entry_developers.c.developer_id)
            .all()
        )
        return dict(rows)

    def count_entries_for_id(self, db: Session, developer_id: str) -> int:
        return (
            db.query(sa.func.count(archive_entry_developers.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_developers.c.archive_entry_id)
            .filter(archive_entry_developers.c.developer_id == developer_id, ArchiveEntry.deleted_at.is_(None))
            .scalar()
        )
