from sqlalchemy.orm import Session

from app.models.library import Library
from app.repositories.base import BaseRepository


class LibraryRepository(BaseRepository[Library]):
    def __init__(self) -> None:
        super().__init__(Library)

    def list_active(self, db: Session, offset: int = 0, limit: int = 100) -> list[Library]:
        return (
            db.query(Library)
            .filter(Library.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_active(self, db: Session, id: str) -> Library | None:
        return db.query(Library).filter(Library.id == id, Library.deleted_at.is_(None)).one_or_none()

    def get_by_name(self, db: Session, name: str) -> Library | None:
        return db.query(Library).filter(Library.name == name, Library.deleted_at.is_(None)).one_or_none()

    def get_by_path(self, db: Session, path: str, edge_id: str | None = None) -> Library | None:
        # Paths are per machine: the same folder name can exist on the server and on each edge device.
        location = Library.edge_id.is_(None) if edge_id is None else Library.edge_id == edge_id
        return db.query(Library).filter(Library.path == path, location, Library.deleted_at.is_(None)).one_or_none()