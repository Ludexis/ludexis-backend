from datetime import datetime, timedelta

from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password, verify_token
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.refresh_token import RefreshTokenRepository
from app.repositories.user import UserRepository


class AuthService:
    def __init__(self) -> None:
        self.user_repo = UserRepository()
        self.refresh_repo = RefreshTokenRepository()

    def authenticate(self, db: Session, username: str, password: str) -> User | None:
        user = self.user_repo.get_by_username(db, username)
        if not user or not verify_password(password, user.hashed_password):
            return None
        return user

    def create_tokens(self, db: Session, user: User) -> dict[str, str]:
        access_token = create_access_token(subject=user.id)
        refresh_token = create_refresh_token(subject=user.id)
        expires_at = datetime.utcnow() + timedelta(days=30)
        self.refresh_repo.create(db, {
            "token": refresh_token,
            "user_id": user.id,
            "expires_at": expires_at,
        })
        return {"access_token": access_token, "refresh_token": refresh_token}

    def refresh_tokens(self, db: Session, refresh_token: str) -> dict[str, str]:
        subject = verify_token(refresh_token, token_type="refresh")
        token_record = self.refresh_repo.get_by_token(db, refresh_token)
        if token_record is None or token_record.revoked:
            raise JWTError("Invalid refresh token")
        user = self.user_repo.get(db, subject)
        if user is None or not user.is_active:
            raise JWTError("Inactive user")
        token_record.revoked = True
        db.add(token_record)
        db.commit()
        return self.create_tokens(db, user)

    def logout(self, db: Session, refresh_token: str) -> None:
        token_record = self.refresh_repo.get_by_token(db, refresh_token)
        if token_record:
            token_record.revoked = True
            db.add(token_record)
            db.commit()
