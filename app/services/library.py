from sqlalchemy.orm import Session

from app.models.library import Library
from app.repositories.library import LibraryRepository
from app.schemas.library import LibraryCreate, LibraryUpdate


class LibraryService:
    def __init__(self) -> None:
        self.repo = LibraryRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100) -> list[Library]:
        return self.repo.list_active(db, offset=offset, limit=limit)

    def get(self, db: Session, library_id: str) -> Library | None:
        return self.repo.get_active(db, library_id)

    def create(self, db: Session, data: LibraryCreate) -> Library:
        self._ensure_unique(db, name=data.name, path=data.path)
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, library: Library, data: LibraryUpdate) -> Library:
        update_data = data.model_dump(exclude_none=True)
        self._ensure_unique(
            db,
            name=update_data.get("name"),
            path=update_data.get("path"),
            current_id=library.id,
        )
        return self.repo.update(db, library, update_data)

    def delete(self, db: Session, library: Library) -> Library:
        return self.repo.delete(db, library)

    def _ensure_unique(
        self,
        db: Session,
        name: str | None = None,
        path: str | None = None,
        current_id: str | None = None,
    ) -> None:
        if name is not None:
            existing = self.repo.get_by_name(db, name)
            if existing is not None and existing.id != current_id:
                raise ValueError("Library name already exists")

        if path is not None:
            existing = self.repo.get_by_path(db, path)
            if existing is not None and existing.id != current_id:
                raise ValueError("Library path already exists")