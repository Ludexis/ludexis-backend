from app.models.archive_entry import ArchiveEntry
from app.repositories.archive_entry import ArchiveEntryRepository
from sqlalchemy.orm import Session


class SearchService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()

    def search(
        self,
        db: Session,
        sort: str = "title",
        offset: int = 0,
        limit: int = 100,
        **filters,
    ) -> list[ArchiveEntry]:
        entries = self.repo.search(db, sort=sort, offset=offset, limit=limit, **filters)
        if filters.get("group_versions"):
            counts = self.repo.version_counts(db, {entry.group_key for entry in entries if entry.group_key})
            for entry in entries:
                entry.version_count = counts.get(entry.group_key, 1)
        return entries

    def count(self, db: Session, **filters) -> int:
        return self.repo.count_search(db, **filters)
