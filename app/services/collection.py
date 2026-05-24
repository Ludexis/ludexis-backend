from sqlalchemy.orm import Session

from app.models.collection import Collection
from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.collection import CollectionRepository
from app.schemas.collection import CollectionCreate, CollectionUpdate


class CollectionService:
    def __init__(self) -> None:
        self.repo = CollectionRepository()
        self.entry_repo = ArchiveEntryRepository()

    def list(self, db: Session, offset: int = 0, limit: int = 100) -> list[Collection]:
        return self.repo.list_active(db, offset=offset, limit=limit)

    def get(self, db: Session, collection_id: str) -> Collection | None:
        return self.repo.get_active(db, collection_id)

    def create(self, db: Session, data: CollectionCreate) -> Collection:
        collection_data = data.model_dump(exclude={"entry_ids"})
        collection = self.repo.create(db, collection_data)
        if data.entry_ids:
            collection.archive_entries = self._resolve_entries(db, data.entry_ids)
            db.add(collection)
            db.commit()
            db.refresh(collection)
        return collection

    def update(self, db: Session, collection: Collection, data: CollectionUpdate) -> Collection:
        update_data = data.model_dump(exclude={"entry_ids"}, exclude_none=True)
        collection = self.repo.update(db, collection, update_data)
        if data.entry_ids is not None:
            collection.archive_entries = self._resolve_entries(db, data.entry_ids)
            db.add(collection)
            db.commit()
            db.refresh(collection)
        return collection

    def delete(self, db: Session, collection: Collection) -> Collection:
        return self.repo.delete(db, collection)

    def add_entry(self, db: Session, collection: Collection, entry_id: str) -> Collection:
        entry = self.entry_repo.get_active(db, entry_id)
        if entry is None:
            raise ValueError(f"Archive entry not found: {entry_id}")
        if entry not in collection.archive_entries:
            collection.archive_entries.append(entry)
            db.add(collection)
            db.commit()
            db.refresh(collection)
        return collection

    def remove_entry(self, db: Session, collection: Collection, entry_id: str) -> Collection:
        entry = self.entry_repo.get_active(db, entry_id)
        if entry is None:
            raise ValueError(f"Archive entry not found: {entry_id}")
        if entry in collection.archive_entries:
            collection.archive_entries.remove(entry)
            db.add(collection)
            db.commit()
            db.refresh(collection)
        return collection

    def _resolve_entries(self, db: Session, entry_ids: list[str]) -> list[ArchiveEntry]:
        entries = []
        for entry_id in entry_ids:
            entry = self.entry_repo.get_active(db, entry_id)
            if entry is None:
                raise ValueError(f"Archive entry not found: {entry_id}")
            entries.append(entry)
        return entries
