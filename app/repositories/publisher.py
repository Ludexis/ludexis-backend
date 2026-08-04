import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_publishers
from app.models.publisher import Publisher
from app.repositories.base import BaseRepository


class PublisherRepository(BaseRepository[Publisher]):
    def __init__(self) -> None:
        super().__init__(Publisher)

    def get_by_name(self, db: Session, name: str) -> Publisher | None:
        return db.query(Publisher).filter(Publisher.name == name).one_or_none()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Publisher]:
        query = db.query(Publisher)
        if q:
            query = query.filter(Publisher.name.ilike(f"%{q}%"))
        return query.order_by(Publisher.name).offset(offset).limit(limit).all()

    def count(self, db: Session, q: str | None = None) -> int:
        query = db.query(sa.func.count(Publisher.id))
        if q:
            query = query.filter(Publisher.name.ilike(f"%{q}%"))
        return query.scalar()

    def count_entries_for_ids(self, db: Session, publisher_ids: list[str]) -> dict[str, int]:
        if not publisher_ids:
            return {}
        rows = (
            db.query(archive_entry_publishers.c.publisher_id, sa.func.count(archive_entry_publishers.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_publishers.c.archive_entry_id)
            .filter(archive_entry_publishers.c.publisher_id.in_(publisher_ids), ArchiveEntry.deleted_at.is_(None))
            .group_by(archive_entry_publishers.c.publisher_id)
            .all()
        )
        return dict(rows)

    def count_entries_for_id(self, db: Session, publisher_id: str) -> int:
        return (
            db.query(sa.func.count(archive_entry_publishers.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_publishers.c.archive_entry_id)
            .filter(archive_entry_publishers.c.publisher_id == publisher_id, ArchiveEntry.deleted_at.is_(None))
            .scalar()
        )
