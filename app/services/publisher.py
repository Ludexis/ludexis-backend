from sqlalchemy.orm import Session

from app.models.publisher import Publisher
from app.repositories.publisher import PublisherRepository
from app.schemas.publisher import PublisherCreate, PublisherUpdate


class PublisherService:
    def __init__(self) -> None:
        self.repo = PublisherRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100) -> list[Publisher]:
        return self.repo.list_items(db, offset=offset, limit=limit)

    def get(self, db: Session, publisher_id: str) -> Publisher | None:
        return self.repo.get(db, publisher_id)

    def create(self, db: Session, data: PublisherCreate) -> Publisher:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, publisher: Publisher, data: PublisherUpdate) -> Publisher:
        return self.repo.update(db, publisher, data.model_dump(exclude_none=True))

    def delete(self, db: Session, publisher: Publisher) -> Publisher:
        return self.repo.delete(db, publisher)
