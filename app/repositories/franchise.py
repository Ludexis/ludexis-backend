from sqlalchemy.orm import Session

from app.models.franchise import Franchise
from app.repositories.base import BaseRepository


class FranchiseRepository(BaseRepository[Franchise]):
    def __init__(self) -> None:
        super().__init__(Franchise)

    def get_by_name(self, db: Session, name: str) -> Franchise | None:
        return db.query(Franchise).filter(Franchise.name == name).one_or_none()
