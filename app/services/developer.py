from sqlalchemy.orm import Session

from app.models.developer import Developer
from app.repositories.developer import DeveloperRepository
from app.schemas.developer import DeveloperCreate, DeveloperUpdate


class DeveloperService:
    def __init__(self) -> None:
        self.repo = DeveloperRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100) -> list[Developer]:
        return self.repo.list_items(db, offset=offset, limit=limit)

    def get(self, db: Session, developer_id: str) -> Developer | None:
        return self.repo.get(db, developer_id)

    def create(self, db: Session, data: DeveloperCreate) -> Developer:
        return self.repo.create(db, data.model_dump())

    def update(self, db: Session, developer: Developer, data: DeveloperUpdate) -> Developer:
        return self.repo.update(db, developer, data.model_dump(exclude_none=True))

    def delete(self, db: Session, developer: Developer) -> Developer:
        return self.repo.delete(db, developer)
