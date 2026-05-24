from sqlalchemy.orm import Session

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self) -> None:
        super().__init__(RefreshToken)

    def get_by_token(self, db: Session, token: str) -> RefreshToken | None:
        return db.query(RefreshToken).filter(RefreshToken.token == token).one_or_none()
