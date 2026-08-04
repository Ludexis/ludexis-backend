from sqlalchemy.orm import Session

from app.models.developer import Developer
from app.repositories.developer import DeveloperRepository
from app.schemas.developer import DeveloperCreate, DeveloperUpdate


class DeveloperService:
    def __init__(self) -> None:
        self.repo = DeveloperRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Developer]:
        developers = self.repo.list_items(db, offset=offset, limit=limit, q=q)
        counts = self.repo.count_entries_for_ids(db, [developer.id for developer in developers])
        for developer in developers:
            developer.entry_count = counts.get(developer.id, 0)
        return developers

    def count(self, db: Session, q: str | None = None) -> int:
        return self.repo.count(db, q=q)

    def get(self, db: Session, developer_id: str) -> Developer | None:
        developer = self.repo.get(db, developer_id)
        if developer is not None:
            developer.entry_count = self.repo.count_entries_for_id(db, developer_id)
        return developer

    def create(self, db: Session, data: DeveloperCreate) -> Developer:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, developer: Developer, data: DeveloperUpdate) -> Developer:
        return self.repo.update(db, developer, data.model_dump(exclude_none=True))

    def delete(self, db: Session, developer: Developer) -> Developer:
        return self.repo.delete(db, developer)
