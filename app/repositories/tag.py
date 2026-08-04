import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_tags
from app.models.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self) -> None:
        super().__init__(Tag)

    def get_by_name(self, db: Session, name: str) -> Tag | None:
        return db.query(Tag).filter(Tag.name == name).one_or_none()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Tag]:
        query = db.query(Tag)
        if q:
            query = query.filter(Tag.name.ilike(f"%{q}%"))
        return query.order_by(Tag.name).offset(offset).limit(limit).all()

    def count(self, db: Session, q: str | None = None) -> int:
        query = db.query(sa.func.count(Tag.id))
        if q:
            query = query.filter(Tag.name.ilike(f"%{q}%"))
        return query.scalar()

    def count_entries_for_ids(self, db: Session, tag_ids: list[str]) -> dict[str, int]:
        if not tag_ids:
            return {}
        rows = (
            db.query(archive_entry_tags.c.tag_id, sa.func.count(archive_entry_tags.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_tags.c.archive_entry_id)
            .filter(archive_entry_tags.c.tag_id.in_(tag_ids), ArchiveEntry.deleted_at.is_(None))
            .group_by(archive_entry_tags.c.tag_id)
            .all()
        )
        return dict(rows)

    def count_entries_for_id(self, db: Session, tag_id: str) -> int:
        return (
            db.query(sa.func.count(archive_entry_tags.c.archive_entry_id))
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_tags.c.archive_entry_id)
            .filter(archive_entry_tags.c.tag_id == tag_id, ArchiveEntry.deleted_at.is_(None))
            .scalar()
        )
