from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    get_current_active_user,
    get_current_user,
    require_csrf_header,
    set_auth_cookies,
)
from app.core.config import settings
from app.core.rate_limit import LoginRateLimiter
from app.db.session import get_db
from app.repositories.refresh_token import RefreshTokenRepository
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, LogoutRequest, RefreshRequest, Token
from app.schemas.user import UserRead
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.utils.audit_actions import AuditAction

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()
audit_log_service = AuditService()
refresh_repo = RefreshTokenRepository()
login_limiter = LoginRateLimiter()


def _expiry() -> dict[str, int]:
    return {
        "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        "refresh_expires_in": settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
    }


def _authenticate(db: Session, request: Request, username: str, password: str):
    address = request.client.host if request.client else "unknown"
    retry_after = login_limiter.retry_after(username, address)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    user = auth_service.authenticate(db, username, password)
    if not user:
        login_limiter.record_failure(username, address)
        audit_log_service.log(
            db,
            action=AuditAction.LOGIN_FAILURE,
            entity="User",
            details=f"Login failed for username '{username}'",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user",
        )
    login_limiter.reset(username, address)
    tokens = auth_service.create_tokens(db, user)
    audit_log_service.log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        entity="User",
        entity_id=user.id,
        user_id=user.id,
        details=f"User '{user.username}' logged in",
    )
    return tokens


@router.post(
    "/login",
    response_model=Token,
    summary="Login with credentials",
    description="Authenticate a user, set the session cookies and return access and refresh tokens.",
    response_description="Tokens issued.",
)
def login(data: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)):
    tokens = _authenticate(db, request, data.username, data.password)
    set_auth_cookies(request, response, tokens["access_token"], tokens["refresh_token"])
    return {**tokens, "token_type": "bearer", **_expiry()}


@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Exchange a refresh token (body or cookie) for new tokens. Cookie refreshes only renew the cookies.",
    response_description="Tokens refreshed.",
)
def refresh(request: Request, response: Response, data: RefreshRequest | None = None, db: Session = Depends(get_db)):
    from_cookie = not (data and data.refresh_token)
    refresh_token = request.cookies.get(REFRESH_COOKIE) if from_cookie else data.refresh_token
    if from_cookie:
        require_csrf_header(request)
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    try:
        tokens = auth_service.refresh_tokens(db, refresh_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    token_record = refresh_repo.get_by_token(db, refresh_token)
    if token_record is not None:
        audit_log_service.log(
            db,
            action=AuditAction.TOKEN_REFRESH,
            entity="User",
            entity_id=token_record.user_id,
            user_id=token_record.user_id,
            details="Refresh token used",
        )
    set_auth_cookies(request, response, tokens["access_token"], tokens["refresh_token"])
    if from_cookie:
        return {"token_type": "bearer", **_expiry()}
    return {**tokens, "token_type": "bearer", **_expiry()}


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke the refresh token (body or cookie) and clear the session cookies.",
    response_description="Logout completed.",
)
def logout(request: Request, response: Response, data: LogoutRequest | None = None, db: Session = Depends(get_db)):
    refresh_token = (data.refresh_token if data else None) or request.cookies.get(REFRESH_COOKIE)
    clear_auth_cookies(response)
    if not refresh_token:
        return
    token_record = refresh_repo.get_by_token(db, refresh_token)
    was_revoked = token_record.revoked if token_record is not None else None
    auth_service.logout(db, refresh_token)
    if token_record is not None and not was_revoked:
        audit_log_service.log(
            db,
            action=AuditAction.LOGOUT,
            entity="User",
            entity_id=token_record.user_id,
            user_id=token_record.user_id,
            details="User logged out",
        )


@router.post(
    "/change-password",
    response_model=Token,
    summary="Change own password",
    description="Change the signed-in user's password. Every other session is signed out; this one gets new tokens.",
    response_description="Password changed.",
)
def change_password(
    data: ChangePasswordRequest,
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    address = request.client.host if request.client else "unknown"
    # Guessing the current password from a hijacked session is limited like sign-in.
    retry_after = login_limiter.retry_after(current_user.username, address)
    if retry_after:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed attempts. Try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    if not auth_service.change_password(db, current_user, data.current_password, data.new_password):
        login_limiter.record_failure(current_user.username, address)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    login_limiter.reset(current_user.username, address)
    tokens = auth_service.create_tokens(db, current_user)
    set_auth_cookies(request, response, tokens["access_token"], tokens["refresh_token"])
    audit_log_service.log(
        db, action=AuditAction.CHANGE_PASSWORD, entity="User", entity_id=current_user.id, user_id=current_user.id,
        details="Password changed; other sessions signed out",
    )
    if request.headers.get("Authorization"):
        return {**tokens, "token_type": "bearer", **_expiry()}
    return {"token_type": "bearer", **_expiry()}


@router.post(
    "/logout-all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Log out everywhere",
    description="Sign the current user out of every session on every device, including this one.",
    response_description="All sessions ended.",
)
def logout_all(response: Response, current_user: User = Depends(get_current_active_user), db: Session = Depends(get_db)):
    auth_service.end_sessions(db, current_user)
    clear_auth_cookies(response)
    audit_log_service.log(
        db, action=AuditAction.LOGOUT_ALL, entity="User", entity_id=current_user.id, user_id=current_user.id,
        details="Signed out of every session",
    )


@router.get(
    "/me",
    response_model=UserRead,
    summary="Get current user",
    description="Return the currently authenticated user.",
    response_description="Current user retrieved.",
)
def read_current_user(current_user: UserRead = Depends(get_current_user)):
    return current_user


@router.post(
    "/token",
    response_model=Token,
    summary="OAuth2 password login",
    description="Authenticate using OAuth2 password form and return tokens.",
    response_description="Tokens issued.",
)
def token_login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    tokens = _authenticate(db, request, form_data.username, form_data.password)
    return {**tokens, "token_type": "bearer", **_expiry()}
