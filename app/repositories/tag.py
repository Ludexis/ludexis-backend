from sqlalchemy.orm import Session

from app.models.tag import Tag
from app.repositories.base import BaseRepository


class TagRepository(BaseRepository[Tag]):
    def __init__(self) -> None:
        super().__init__(Tag)

    def get_by_name(self, db: Session, name: str) -> Tag | None:
        return db.query(Tag).filter(Tag.name == name).one_or_none()
