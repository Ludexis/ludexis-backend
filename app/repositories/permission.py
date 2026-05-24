from sqlalchemy.orm import Session

from app.models.permission import Permission
from app.repositories.base import BaseRepository


class PermissionRepository(BaseRepository[Permission]):
    def __init__(self) -> None:
        super().__init__(Permission)

    def get_by_name(self, db: Session, name: str) -> Permission | None:
        return db.query(Permission).filter(Permission.name == name).one_or_none()
