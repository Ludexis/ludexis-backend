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

    def list_active(self, db: Session, offset: int = 0, limit: int = 100) -> list[ArchiveEntry]:
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

    def get_by_title_and_version(
        self,
        db: Session,
        title: str,
        version: str | None,
    ) -> ArchiveEntry | None:
        query = (
            db.query(ArchiveEntry)
            .filter(
                sa.func.lower(ArchiveEntry.title) == title.lower(),
                ArchiveEntry.deleted_at.is_(None),
            )
        )
        if version is None:
            query = query.filter(ArchiveEntry.version.is_(None))
        else:
            query = query.filter(ArchiveEntry.version == version)
        return query.one_or_none()


    def list_titles(self, db: Session) -> list[str]:
        rows = db.query(ArchiveEntry.title).filter(ArchiveEntry.deleted_at.is_(None)).all()
        return [row[0] for row in rows]

    def list_all(self, db: Session) -> list[ArchiveEntry]:
        return db.query(ArchiveEntry).all()

    def search(
        self,
        db: Session,
        query: str | None = None,
        genre: str | None = None,
        tag: str | None = None,
        developer: str | None = None,
        publisher: str | None = None,
        collection: str | None = None,
        franchise: str | None = None,
        metadata_status: str | None = None,
        verification_status: str | None = None,
        storage_device: str | None = None,
        offset: int = 0,
        limit: int = 100,
    ) -> list[ArchiveEntry]:
        filters = [ArchiveEntry.deleted_at.is_(None)]

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

        if franchise:
            filters.append(ArchiveEntry.franchise.has(Franchise.name == franchise))

        if metadata_status:
            filters.append(ArchiveEntry.metadata_status == metadata_status)

        if verification_status:
            filters.append(ArchiveEntry.verification_status == verification_status)

        if storage_device:
            filters.append(ArchiveEntry.storage_device.ilike(f"%{storage_device}%"))

        return (
            db.query(ArchiveEntry)
            .filter(*filters)
            .offset(offset)
            .limit(limit)
            .all()
        )
    
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