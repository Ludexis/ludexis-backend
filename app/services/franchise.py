from sqlalchemy.orm import Session

from app.models.franchise import Franchise
from app.repositories.franchise import FranchiseRepository
from app.schemas.franchise import FranchiseCreate, FranchiseUpdate


class FranchiseService:
    def __init__(self) -> None:
        self.repo = FranchiseRepository()

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None) -> list[Franchise]:
        franchises = self.repo.list_items(db, offset=offset, limit=limit, q=q)
        counts = self.repo.count_entries_for_ids(db, [franchise.id for franchise in franchises])
        for franchise in franchises:
            franchise.entry_count = counts.get(franchise.id, 0)
        return franchises

    def count(self, db: Session, q: str | None = None) -> int:
        return self.repo.count(db, q=q)

    def get(self, db: Session, franchise_id: str) -> Franchise | None:
        franchise = self.repo.get(db, franchise_id)
        if franchise is not None:
            franchise.entry_count = self.repo.count_entries_for_id(db, franchise_id)
        return franchise

    def create(self, db: Session, data: FranchiseCreate) -> Franchise:
        franchise_data = data.model_dump(exclude={"child_ids"})
        return self.repo.create(db, franchise_data)

    def update(self, db: Session, franchise: Franchise, data: FranchiseUpdate) -> Franchise:
        update_data = data.model_dump(exclude={"child_ids"}, exclude_none=True)
        return self.repo.update(db, franchise, update_data)

    def delete(self, db: Session, franchise: Franchise) -> Franchise:
        return self.repo.delete(db, franchise)
