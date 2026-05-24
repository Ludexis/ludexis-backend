from sqlalchemy.orm import Session

from app.models.developer import Developer
from app.repositories.base import BaseRepository


class DeveloperRepository(BaseRepository[Developer]):
    def __init__(self) -> None:
        super().__init__(Developer)

    def get_by_name(self, db: Session, name: str) -> Developer | None:
        return db.query(Developer).filter(Developer.name == name).one_or_none()
