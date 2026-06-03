from sqlalchemy.orm import Session

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