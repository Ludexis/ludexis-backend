from sqlalchemy.orm import Session

from app.models.role import Role
from app.repositories.base import BaseRepository


class RoleRepository(BaseRepository[Role]):
    def __init__(self) -> None:
        super().__init__(Role)

    def get_by_name(self, db: Session, name: str) -> Role | None:
        return db.query(Role).filter(Role.name == name).one_or_none()
