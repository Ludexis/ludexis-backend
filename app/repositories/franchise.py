import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.franchise import Franchise
from app.repositories.base import BaseRepository
from app.core.access import entry_filters, visible_names


class FranchiseRepository(BaseRepository[Franchise]):
    def __init__(self) -> None:
        super().__init__(Franchise)

    def get_by_name(self, db: Session, name: str) -> Franchise | None:
        return db.query(Franchise).filter(Franchise.name == name).one_or_none()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None, viewer=None) -> list[Franchise]:
        query = db.query(Franchise).filter(visible_names(Franchise.archive_entries, viewer))
        if q:
            query = query.filter(Franchise.name.ilike(f"%{q}%"))
        return query.order_by(Franchise.name).offset(offset).limit(limit).all()

    def count(self, db: Session, q: str | None = None, viewer=None) -> int:
        query = db.query(sa.func.count(Franchise.id)).filter(visible_names(Franchise.archive_entries, viewer))
        if q:
            query = query.filter(Franchise.name.ilike(f"%{q}%"))
        return query.scalar()

    def count_entries_for_ids(self, db: Session, franchise_ids: list[str], viewer=None) -> dict[str, int]:
        if not franchise_ids:
            return {}
        rows = (
            db.query(ArchiveEntry.franchise_id, sa.func.count(ArchiveEntry.id))
            .filter(ArchiveEntry.franchise_id.in_(franchise_ids), ArchiveEntry.deleted_at.is_(None), *entry_filters(viewer))
            .group_by(ArchiveEntry.franchise_id)
            .all()
        )
        return dict(rows)

    def count_entries_for_id(self, db: Session, franchise_id: str, viewer=None) -> int:
        return (
            db.query(sa.func.count(ArchiveEntry.id))
            .filter(ArchiveEntry.franchise_id == franchise_id, ArchiveEntry.deleted_at.is_(None), *entry_filters(viewer))
            .scalar()
        )
