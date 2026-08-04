from sqlalchemy.orm import Session

from app.models.publisher import Publisher
from app.repositories.publisher import PublisherRepository
from app.schemas.publisher import PublisherCreate, PublisherUpdate


class PublisherService:
    def __init__(self) -> None:
        self.repo = PublisherRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Publisher]:
        publishers = self.repo.list_items(db, offset=offset, limit=limit, q=q)
        counts = self.repo.count_entries_for_ids(db, [publisher.id for publisher in publishers])
        for publisher in publishers:
            publisher.entry_count = counts.get(publisher.id, 0)
        return publishers

    def count(self, db: Session, q: str | None = None) -> int:
        return self.repo.count(db, q=q)

    def get(self, db: Session, publisher_id: str) -> Publisher | None:
        publisher = self.repo.get(db, publisher_id)
        if publisher is not None:
            publisher.entry_count = self.repo.count_entries_for_id(db, publisher_id)
        return publisher

    def create(self, db: Session, data: PublisherCreate) -> Publisher:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, publisher: Publisher, data: PublisherUpdate) -> Publisher:
        return self.repo.update(db, publisher, data.model_dump(exclude_none=True))

    def delete(self, db: Session, publisher: Publisher) -> Publisher:
        return self.repo.delete(db, publisher)
