from typing import Optional

from app.models.archive_entry import ArchiveEntry
from app.models.developer import Developer
from app.models.genre import Genre
from app.models.publisher import Publisher
from app.models.tag import Tag
from app.repositories.archive_entry import ArchiveEntryRepository
from app.schemas.archive_entry import ArchiveEntryRead
from sqlalchemy import or_
from sqlalchemy.orm import Session


class SearchService:
    def __init__(self) -> None:
        self.repo = ArchiveEntryRepository()

    def search(
        self,
        db: Session,
        query: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        developer: str | None = None,
        publisher: str | None = None,
        franchise: str | None = None,
        metadata_status: str | None = None,
        verification_status: str | None = None,
        storage_device: str | None = None,
        group_versions: bool = False,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ArchiveEntry]:
        entries = self.repo.search(
            db,
            query=query,
            genre=genre,
            tag=tag,
            developer=developer,
            publisher=publisher,
            franchise=franchise,
            metadata_status=metadata_status,
            verification_status=verification_status,
            storage_device=storage_device,
            group_versions=group_versions,
            offset=offset,
            limit=limit,
        )
        if group_versions:
            counts = self.repo.version_counts(db, {entry.group_key for entry in entries if entry.group_key})
            for entry in entries:
                entry.version_count = counts.get(entry.group_key, 1)
        return entries
