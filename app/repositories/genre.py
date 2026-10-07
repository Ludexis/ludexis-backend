import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_genres

from app.models.genre import Genre
from app.repositories.base import BaseRepository


class GenreRepository(BaseRepository[Genre]):
    def __init__(self) -> None:
        super().__init__(Genre)

    def get_by_name(
        self,
        db: Session,
        name: str,
    ) -> Genre | None:
        return (
            db.query(Genre)
            .filter(
                Genre.name == name
            )
            .one_or_none()
        )

    def list_with_counts(self, db: Session) -> list[tuple[str, int]]:
        """Genre names with their number of live entries; genres with none are left out."""
        entry_count = sa.func.count(ArchiveEntry.id)
        return (
            db.query(Genre.name, entry_count)
            .join(archive_entry_genres, archive_entry_genres.c.genre_id == Genre.id)
            .join(ArchiveEntry, ArchiveEntry.id == archive_entry_genres.c.archive_entry_id)
            .filter(ArchiveEntry.deleted_at.is_(None))
            .group_by(Genre.name)
            .order_by(Genre.name)
            .all()
        )
