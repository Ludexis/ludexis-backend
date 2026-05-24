from sqlalchemy.orm import Session

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self) -> None:
        super().__init__(User)

    def get_by_email(self, db: Session, email: str) -> User | None:
        return db.query(User).filter(User.email == email, User.deleted_at.is_(None)).one_or_none()

    def get_by_username(self, db: Session, username: str) -> User | None:
        return db.query(User).filter(User.username == username, User.deleted_at.is_(None)).one_or_none()

    def activate(self, db: Session, user: User) -> User:
        user.is_active = True
        return self.update(db, user, {})

    def deactivate(self, db: Session, user: User) -> User:
        user.is_active = False
        return self.update(db, user, {})
