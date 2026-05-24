from sqlalchemy.orm import Session

from app.models.publisher import Publisher
from app.repositories.base import BaseRepository


class PublisherRepository(BaseRepository[Publisher]):
    def __init__(self) -> None:
        super().__init__(Publisher)

    def get_by_name(self, db: Session, name: str) -> Publisher | None:
        return db.query(Publisher).filter(Publisher.name == name).one_or_none()
