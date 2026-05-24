from sqlalchemy.orm import Session

from app.models.franchise import Franchise
from app.repositories.franchise import FranchiseRepository
from app.schemas.franchise import FranchiseCreate, FranchiseUpdate


class FranchiseService:
    def __init__(self) -> None:
        self.repo = FranchiseRepository()

    def list(self, db: Session, offset: int = 0, limit: int = 100) -> list[Franchise]:
        return self.repo.list(db, offset=offset, limit=limit)

    def get(self, db: Session, franchise_id: str) -> Franchise | None:
        return self.repo.get(db, franchise_id)

    def create(self, db: Session, data: FranchiseCreate) -> Franchise:
        franchise_data = data.model_dump(exclude={"child_ids"})
        return self.repo.create(db, franchise_data)

    def update(self, db: Session, franchise: Franchise, data: FranchiseUpdate) -> Franchise:
        update_data = data.model_dump(exclude={"child_ids"}, exclude_none=True)
        return self.repo.update(db, franchise, update_data)

    def delete(self, db: Session, franchise: Franchise) -> Franchise:
        return self.repo.delete(db, franchise)
