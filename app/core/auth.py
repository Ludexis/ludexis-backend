from datetime import datetime, UTC

from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import verify_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.utils.enums import PermissionName
from app.db.session import get_db

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token"
)

oauth2_scheme_optional = OAuth2PasswordBearer(
    tokenUrl="/api/auth/token",
    auto_error=False,
)
user_repo = UserRepository()

# The browser app authenticates with httpOnly cookies; tools keep using the Authorization header.
ACCESS_COOKIE = "ludexis_access"
REFRESH_COOKIE = "ludexis_refresh"
CSRF_HEADER = "X-Requested-With"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def require_csrf_header(request: Request) -> None:
    # A cross-site form cannot set custom headers, so cookie-authenticated writes must carry this one.
    if request.method in UNSAFE_METHODS and not request.headers.get(CSRF_HEADER):
        raise HTTPException(status_code=403, detail=f"Missing {CSRF_HEADER} header")


def request_token(request: Request, header_token: str | None) -> str | None:
    if header_token:
        return header_token
    cookie = request.cookies.get(ACCESS_COOKIE)
    if cookie:
        require_csrf_header(request)
    return cookie


def set_auth_cookies(request: Request, response: Response, access_token: str, refresh_token: str) -> None:
    secure = request.url.scheme == "https"
    response.set_cookie(
        ACCESS_COOKIE, access_token, max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True, samesite="lax", secure=secure, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh_token, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True, samesite="lax", secure=secure, path=f"{settings.API_PREFIX}/auth",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path=f"{settings.API_PREFIX}/auth")


def _user_from_token(token: str, db: Session) -> User:
    try:
        subject = verify_token(token, token_type="access")
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials") from exc
    user = user_repo.get(db, subject)
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Inactive user")
    return user


def get_current_user(request: Request, token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> User:
    token = request_token(request, token)
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated", headers={"WWW-Authenticate": "Bearer"})
    return _user_from_token(token, db)


def get_optional_current_user(request: Request, token: str | None = Depends(oauth2_scheme_optional), db: Session = Depends(get_db)) -> User | None:
    token = request_token(request, token)
    if not token:
        return None
    return _user_from_token(token, db)


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
