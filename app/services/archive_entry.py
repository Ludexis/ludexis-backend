from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.collection import CollectionRepository
from app.repositories.developer import DeveloperRepository
from app.repositories.franchise import FranchiseRepository
from app.repositories.publisher import PublisherRepository
from app.repositories.tag import TagRepository
from app.schemas.archive_entry import ArchiveEntryCreate, ArchiveEntryUpdate


class ArchiveEntryService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()
        self.tag_repo = TagRepository()
        self.developer_repo = DeveloperRepository()
        self.publisher_repo = PublisherRepository()
        self.collection_repo = CollectionRepository()
        self.franchise_repo = FranchiseRepository()

    def list(self, db: Session, offset: int = 0, limit: int = 100) -> list[ArchiveEntry]:
        return self.repo.list_active(db, offset=offset, limit=limit)

    def get(self, db: Session, entry_id: str) -> ArchiveEntry | None:
        return self.repo.get_active(db, entry_id)

    def create(self, db: Session, data: ArchiveEntryCreate) -> ArchiveEntry:
        entry_data = data.model_dump(exclude={"tag_ids", "developer_ids", "publisher_ids", "collection_ids", "related_entry_ids"})
        entry = self.repo.create(db, entry_data)
        self._assign_relations(db, entry, data)
        return entry

    def update(self, db: Session, entry: ArchiveEntry, data: ArchiveEntryUpdate) -> ArchiveEntry:
        update_data = data.model_dump(exclude={"tag_ids", "developer_ids", "publisher_ids", "collection_ids", "related_entry_ids"}, exclude_none=False)
        entry = self.repo.update(db, entry, update_data)
        self._assign_relations(db, entry, data)
        return entry

    def delete(self, db: Session, entry: ArchiveEntry) -> ArchiveEntry:
        return self.repo.delete(db, entry)

    def _assign_relations(self, db: Session, entry: ArchiveEntry, data: ArchiveEntryCreate | ArchiveEntryUpdate) -> None:
        if hasattr(data, "tag_ids"):
            entry.tags = self._resolve_list(db, data.tag_ids, self.tag_repo, "Tag")
        if hasattr(data, "developer_ids"):
            entry.developers = self._resolve_list(db, data.developer_ids, self.developer_repo, "Developer")
        if hasattr(data, "publisher_ids"):
            entry.publishers = self._resolve_list(db, data.publisher_ids, self.publisher_repo, "Publisher")
        if hasattr(data, "collection_ids"):
            entry.collections = self._resolve_list(db, data.collection_ids, self.collection_repo, "Collection")
        if hasattr(data, "related_entry_ids"):
            entry.related_entries = self._resolve_list(db, data.related_entry_ids, self.repo, "ArchiveEntry")
        if hasattr(data, "franchise_id") and data.franchise_id is not None:
            franchise = self.franchise_repo.get(db, data.franchise_id)
            if franchise is None:
                raise ValueError(f"Franchise not found: {data.franchise_id}")
            entry.franchise = franchise
        if hasattr(data, "parent_series_id") and data.parent_series_id is not None:
            parent_series = self.repo.get_active(db, data.parent_series_id)
            if parent_series is None:
                raise ValueError(f"Parent series not found: {data.parent_series_id}")
            entry.parent_series = parent_series
        db.add(entry)
        db.commit()
        db.refresh(entry)

    def _resolve_list(self, db: Session, ids: list[str] | None, repo, entity_name: str) -> list:
        results = []
        if not ids:
            return []
        for item_id in ids:
            if hasattr(repo, "get_active"):
                item = repo.get_active(db, item_id)
            else:
                item = repo.get(db, item_id)
            if item is None:
                raise ValueError(f"{entity_name} not found: {item_id}")
            results.append(item)
        return results
