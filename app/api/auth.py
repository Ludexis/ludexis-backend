from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.repositories.refresh_token import RefreshTokenRepository
from app.schemas.auth import LoginRequest, Token, RefreshRequest, LogoutRequest
from app.schemas.user import UserRead
from app.services.auth import AuthService
from app.services.audit_log import AuditLogService
from app.utils.audit_actions import AuditAction

from fastapi.security import OAuth2PasswordRequestForm

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()
audit_log_service = AuditLogService()
refresh_repo = RefreshTokenRepository()

@router.post(
    "/login",
    response_model=Token,
    summary="Login with credentials",
    description="Authenticate a user and return access and refresh tokens.",
    response_description="Tokens issued.",
)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, data.username, data.password)
    if not user:
        audit_log_service.log(
            db,
            action=AuditAction.LOGIN_FAILURE,
            entity="User",
            details=f"Login failed for username '{data.username}'",
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
    tokens = auth_service.create_tokens(db, user)
    audit_log_service.log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        entity="User",
        entity_id=user.id,
        user_id=user.id,
        details=f"User '{user.username}' logged in",
    )
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }

@router.post(
    "/refresh",
    response_model=Token,
    summary="Refresh access token",
    description="Exchange a valid refresh token for new tokens.",
    response_description="Tokens refreshed.",
)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        tokens = auth_service.refresh_tokens(db, data.refresh_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    token_record = refresh_repo.get_by_token(db, data.refresh_token)
    if token_record is not None:
        audit_log_service.log(
            db,
            action=AuditAction.TOKEN_REFRESH,
            entity="User",
            entity_id=token_record.user_id,
            user_id=token_record.user_id,
            details="Refresh token used",
        )
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout",
    description="Revoke the provided refresh token.",
    response_description="Logout completed.",
)
def logout(data: LogoutRequest, db: Session = Depends(get_db)):
    token_record = refresh_repo.get_by_token(db, data.refresh_token)
    was_revoked = token_record.revoked if token_record is not None else None
    auth_service.logout(db, data.refresh_token)
    if token_record is not None and not was_revoked:
        audit_log_service.log(
            db,
            action=AuditAction.LOGOUT,
            entity="User",
            entity_id=token_record.user_id,
            user_id=token_record.user_id,
            details="User logged out",
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
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user = auth_service.authenticate(
        db,
        form_data.username,
        form_data.password,
    )

    if not user:
        audit_log_service.log(
            db,
            action=AuditAction.LOGIN_FAILURE,
            entity="User",
            details=f"Login failed for username '{form_data.username}'",
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

    tokens = auth_service.create_tokens(db, user)
    audit_log_service.log(
        db,
        action=AuditAction.LOGIN_SUCCESS,
        entity="User",
        entity_id=user.id,
        user_id=user.id,
        details=f"User '{user.username}' logged in",
    )

    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }