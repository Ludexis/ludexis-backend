import sqlalchemy as sa
from sqlalchemy import select
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
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
        query_builder = db.query(ArchiveEntry)
        query_builder = query_builder.outerjoin(ArchiveEntry.genres)
        query_builder = query_builder.outerjoin(ArchiveEntry.tags)
        query_builder = query_builder.outerjoin(ArchiveEntry.developers)
        query_builder = query_builder.outerjoin(ArchiveEntry.publishers)
        query_builder = query_builder.outerjoin(ArchiveEntry.collections)
        query_builder = query_builder.outerjoin(ArchiveEntry.franchise)

        filters = [ArchiveEntry.deleted_at.is_(None)]

        if query:
            search_value = f"%{query}%"
            filters.append(
                sa.or_(
                    ArchiveEntry.title.ilike(search_value),
                    ArchiveEntry.description.ilike(search_value),
                    Collection.name.ilike(search_value),
                    Developer.name.ilike(search_value),
                    Publisher.name.ilike(search_value),
                    Tag.name.ilike(search_value),
                )
            )

        if genre:
            filters.append(Genre.name == genre)

        if tag:
            filters.append(Tag.name == tag)

        if developer:
            filters.append(Developer.name == developer)

        if publisher:
            filters.append(Publisher.name == publisher)

        if collection:
            filters.append(Collection.name == collection)

        if franchise:
            filters.append(Franchise.name == franchise)

        if metadata_status:
            filters.append(ArchiveEntry.metadata_status == metadata_status)

        if verification_status:
            filters.append(ArchiveEntry.verification_status == verification_status)

        if storage_device:
            filters.append(ArchiveEntry.storage_device.ilike(f"%{storage_device}%"))

        query_builder = query_builder.filter(*filters).distinct().offset(offset).limit(limit)
        return query_builder.all()
