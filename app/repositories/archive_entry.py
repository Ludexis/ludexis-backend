import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import (
    archive_entry_developers,
    archive_entry_publishers,
    archive_entry_tags,
    collection_entries,
)
from app.models.collection import Collection
from app.models.developer import Developer
from app.models.franchise import Franchise
from app.models.genre import Genre
from app.models.publisher import Publisher
from app.models.tag import Tag
from app.repositories.base import BaseRepository


class ArchiveEntryRepository(BaseRepository[ArchiveEntry]):
    def __init__(self) -> None:
        super().__init__(ArchiveEntry)

    def list_active(self, db: Session, offset: int = 0, limit: int | None = 100) -> list[ArchiveEntry]:
        return (
            db.query(ArchiveEntry)
            .filter(ArchiveEntry.deleted_at.is_(None))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def get_active(self, db: Session, id: str) -> ArchiveEntry | None:
        return db.query(ArchiveEntry).filter(ArchiveEntry.id == id, ArchiveEntry.deleted_at.is_(None)).one_or_none()

    def get_by_file_path(self, db: Session, file_path: str) -> ArchiveEntry | None:
        return db.query(ArchiveEntry).filter(ArchiveEntry.file_path == file_path, ArchiveEntry.deleted_at.is_(None)).one_or_none()

    def get_by_hash(self, db: Session, file_hash: str, ) -> ArchiveEntry | None:
        return (db.query(ArchiveEntry).filter(ArchiveEntry.file_hash == file_hash, ArchiveEntry.deleted_at.is_(None),).one_or_none())
    
    def get_by_title(self, db: Session, title: str) -> ArchiveEntry | None:
        return db.query(ArchiveEntry).filter(sa.func.lower(ArchiveEntry.title) == title.lower(), ArchiveEntry.deleted_at.is_(None)).one_or_none()

    def get_by_relative_path(self, db: Session, library_id: str, relative_path: str) -> ArchiveEntry | None:
        return (
            db.query(ArchiveEntry)
            .filter(
                ArchiveEntry.library_id == library_id,
                ArchiveEntry.relative_path == relative_path,
                ArchiveEntry.deleted_at.is_(None),
            )
            .first()
        )

    def list_in_library(self, db: Session, library_id: str) -> list[ArchiveEntry]:
        return db.query(ArchiveEntry).filter(ArchiveEntry.library_id == library_id, ArchiveEntry.deleted_at.is_(None)).all()

    def count_in_library(self, db: Session, library_id: str) -> int:
        return db.query(ArchiveEntry).filter(ArchiveEntry.library_id == library_id, ArchiveEntry.deleted_at.is_(None)).count()

    def list_all(self, db: Session) -> list[ArchiveEntry]:
        return db.query(ArchiveEntry).all()

    SORT_COLUMNS = {
        "title": sa.func.lower(ArchiveEntry.title),
        "created_at": ArchiveEntry.created_at,
        "release_date": ArchiveEntry.release_date,
        "file_size": ArchiveEntry.file_size,
        # Home's "Rediscover" shelf; a fresh shuffle on every request.
        "random": sa.func.random(),
    }

    def search(
        self,
        db: Session,
        sort: str = "title",
        offset: int = 0,
        limit: int = 100,
        **filters,
    ) -> list[ArchiveEntry]:
        descending = sort.startswith("-")
        column = self.SORT_COLUMNS[sort.lstrip("-")]
        order = (column.desc() if descending else column.asc()).nulls_last()
        return (
            db.query(ArchiveEntry)
            .filter(*self._search_filters(**filters))
            .order_by(order, ArchiveEntry.id)
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_search(self, db: Session, **filters) -> int:
        return db.query(ArchiveEntry).filter(*self._search_filters(**filters)).count()

    def _search_filters(
        self,
        query: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        developer: str | None = None,
        publisher: str | None = None,
        collection: str | None = None,
        collection_id: str | None = None,
        franchise: str | None = None,
        metadata_status: str | None = None,
        verification_status: str | None = None,
        storage_device: str | None = None,
        group_versions: bool = False,
        hidden_collection_ids: list[str] | None = None,
    ) -> list:
        filters = [ArchiveEntry.deleted_at.is_(None)]
        if group_versions:
            filters.append(ArchiveEntry.is_primary_version.is_(True))

        # Games in a hidden collection stay out of every listing except that collection's own page.
        hidden = [collection for collection in hidden_collection_ids or [] if collection != collection_id]
        if hidden:
            filters.append(~ArchiveEntry.collections.any(Collection.id.in_(hidden)))

        if query:
            search_value = f"%{query}%"
            text_matches = sa.union(
                sa.select(ArchiveEntry.id.label("id")).where(ArchiveEntry.title.ilike(search_value)),
                sa.select(ArchiveEntry.id.label("id")).where(ArchiveEntry.description.ilike(search_value)),
                sa.select(collection_entries.c.archive_entry_id.label("id"))
                .select_from(collection_entries.join(Collection, Collection.id == collection_entries.c.collection_id))
                .where(Collection.name.ilike(search_value)),
                sa.select(archive_entry_developers.c.archive_entry_id.label("id"))
                .select_from(archive_entry_developers.join(Developer, Developer.id == archive_entry_developers.c.developer_id))
                .where(Developer.name.ilike(search_value)),
                sa.select(archive_entry_publishers.c.archive_entry_id.label("id"))
                .select_from(archive_entry_publishers.join(Publisher, Publisher.id == archive_entry_publishers.c.publisher_id))
                .where(Publisher.name.ilike(search_value)),
                sa.select(archive_entry_tags.c.archive_entry_id.label("id"))
                .select_from(archive_entry_tags.join(Tag, Tag.id == archive_entry_tags.c.tag_id))
                .where(Tag.name.ilike(search_value)),
            ).subquery()
            filters.append(ArchiveEntry.id.in_(sa.select(text_matches.c.id)))

        if genre:
            filters.append(ArchiveEntry.genres.any(Genre.name == genre))

        if tag:
            filters.append(ArchiveEntry.tags.any(Tag.name == tag))

        if developer:
            filters.append(ArchiveEntry.developers.any(Developer.name == developer))

        if publisher:
            filters.append(ArchiveEntry.publishers.any(Publisher.name == publisher))

        if collection:
            filters.append(ArchiveEntry.collections.any(Collection.name == collection))

        if collection_id:
            filters.append(ArchiveEntry.collections.any(Collection.id == collection_id))

        if franchise:
            filters.append(ArchiveEntry.franchise.has(Franchise.name == franchise))

        if metadata_status:
            filters.append(ArchiveEntry.metadata_status == metadata_status)

        if verification_status:
            filters.append(ArchiveEntry.verification_status == verification_status)

        if storage_device:
            filters.append(ArchiveEntry.storage_device.ilike(f"%{storage_device}%"))

        return filters
    
    def get_all_by_hash(
        self,
        db: Session,
        file_hash: str,
    ) -> list[ArchiveEntry]:
        return (
            db.query(ArchiveEntry)
            .filter(
                ArchiveEntry.file_hash == file_hash,
                ArchiveEntry.deleted_at.is_(None),
            )
            .all()
        )

    def version_counts(self, db: Session, group_keys: set[str]) -> dict[str, int]:
        if not group_keys:
            return {}
        rows = (
            db.query(ArchiveEntry.group_key, sa.func.count(ArchiveEntry.id))
            .filter(ArchiveEntry.group_key.in_(group_keys), ArchiveEntry.deleted_at.is_(None))
            .group_by(ArchiveEntry.group_key)
            .all()
        )
        return dict(rows)

    def list_versions(self, db: Session, entry: ArchiveEntry) -> list[ArchiveEntry]:
        if not entry.group_key:
            return [entry]
        return (
            db.query(ArchiveEntry)
            .filter(ArchiveEntry.group_key == entry.group_key, ArchiveEntry.deleted_at.is_(None))
            .all()
        )

    def list_with_hashes(
        self,
        db: Session,
    ) -> list[ArchiveEntry]:
        return (
            db.query(ArchiveEntry)
            .filter(
                ArchiveEntry.deleted_at.is_(None),
                ArchiveEntry.file_hash.is_not(None),
            )
            .all()
        )