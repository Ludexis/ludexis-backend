from sqlalchemy.orm import Session

from app.models.collection import Collection
from app.repositories.base import BaseRepository


class CollectionRepository(BaseRepository[Collection]):
    def __init__(self) -> None:
        super().__init__(Collection)

    def get_by_name(self, db: Session, name: str) -> Collection | None:
        return db.query(Collection).filter(Collection.name == name, Collection.deleted_at.is_(None)).one_or_none()
