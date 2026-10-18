from sqlalchemy.orm import Session

from app.models.edge_device import EdgeDevice
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
        self._ensure_edge(db, data.edge_id)
        self._ensure_unique(db, name=data.name, path=data.path, edge_id=data.edge_id)
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, library: Library, data: LibraryUpdate) -> Library:
        update_data = data.model_dump(exclude_none=True)
        moved = "edge_id" in data.model_fields_set and data.edge_id != library.edge_id
        if moved:
            self._ensure_edge(db, data.edge_id)
            update_data["edge_id"] = data.edge_id
            # The drive is learnt again by the first scan on the new machine.
            update_data.update({"drive_id": None, "drive_subpath": None, "drive_mount": None})
        self._ensure_unique(
            db,
            name=update_data.get("name"),
            path=update_data.get("path", library.path) if moved or "path" in update_data else None,
            current_id=library.id,
            edge_id=update_data.get("edge_id", library.edge_id),
        )
        return self.repo.update(db, library, update_data)

    def _ensure_edge(self, db: Session, edge_id: str | None) -> None:
        if edge_id is not None and db.get(EdgeDevice, edge_id) is None:
            raise ValueError("Edge device not found")

    def delete(self, db: Session, library: Library) -> Library:
        return self.repo.delete(db, library)

    def _ensure_unique(
        self,
        db: Session,
        name: str | None = None,
        path: str | None = None,
        current_id: str | None = None,
        edge_id: str | None = None,
    ) -> None:
        if name is not None:
            existing = self.repo.get_by_name(db, name)
            if existing is not None and existing.id != current_id:
                raise ValueError("Library name already exists")

        if path is not None:
            existing = self.repo.get_by_path(db, path, edge_id)
            if existing is not None and existing.id != current_id:
                raise ValueError("Library path already exists")