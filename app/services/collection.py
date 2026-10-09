from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.association_tables import collection_entries
from app.models.collection import Collection
from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.collection import CollectionRepository
from app.schemas.collection import CollectionCreate, CollectionRead, CollectionUpdate
from app.core.access import entry_filters


class CollectionService:
    def __init__(self) -> None:
        self.repo = CollectionRepository()
        self.entry_repo = ArchiveEntryRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None, viewer=None) -> list[Collection]:
        blocked = viewer.blocked_collection_ids if viewer else None
        return self.repo.list_active(db, offset=offset, limit=limit, q=q, exclude_ids=blocked)

    def get(self, db: Session, collection_id: str, viewer=None) -> Collection | None:
        if viewer is not None and collection_id in viewer.blocked_collection_ids:
            return None
        return self.repo.get_active(db, collection_id)

    def read(self, db: Session, collections: list[Collection], viewer=None) -> list[CollectionRead]:
        """Responses whose entry_ids hold only the live games this viewer may see."""
        visible = defaultdict(list)
        if collections:
            rows = (
                db.query(collection_entries.c.collection_id, ArchiveEntry.id)
                .join(ArchiveEntry, ArchiveEntry.id == collection_entries.c.archive_entry_id)
                .filter(
                    collection_entries.c.collection_id.in_([collection.id for collection in collections]),
                    ArchiveEntry.deleted_at.is_(None),
                    *entry_filters(viewer),
                )
            )
            for collection_id, entry_id in rows:
                visible[collection_id].append(entry_id)
        return [
            CollectionRead.model_validate(collection).model_copy(update={"entry_ids": visible[collection.id]})
            for collection in collections
        ]

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
