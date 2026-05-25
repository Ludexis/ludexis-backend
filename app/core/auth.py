from datetime import datetime

from fastapi import Depends, HTTPException, Security
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.enums import PermissionName
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)
user_repo = UserRepository()


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        subject = verify_token(token, token_type="access")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc
    user = user_repo.get(db, subject)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


def get_optional_current_user(token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> User | None:
    if not token:
        return None
    try:
        subject = verify_token(token, token_type="access")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc
    user = user_repo.get(db, subject)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def ensure_permission(current_user: User, permission: PermissionName) -> None:
    role_permissions = {perm.name for role in current_user.roles for perm in role.permissions}
    if permission.value not in role_permissions and not current_user.is_superuser:
        raise HTTPException(status_code=403, detail="Permission denied")


def require_permission(permission: PermissionName):
    def permission_dependency(current_user: User = Depends(get_current_active_user)) -> User:
        ensure_permission(current_user, permission)
        return current_user

    return permission_dependency
