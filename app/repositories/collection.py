from sqlalchemy.orm import Session

from app.models.collection import Collection
from app.repositories.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    def __init__(self) -> None:
        super().__init__(Collection)

    def list_active(self, db: Session, offset: int = 0, limit: int = 100) -> list[Collection]:
        return (
            db.query(Collection)
            .filter(Collection.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_active(self, db: Session, id: str) -> Collection | None:
        return db.query(Collection).filter(Collection.id == id, Collection.deleted_at.is_(None)).one_or_none()

    def get_by_name(self, db: Session, name: str) -> Collection | None:
        return db.query(Collection).filter(Collection.name == name, Collection.deleted_at.is_(None)).one_or_none()
