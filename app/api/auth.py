from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.session import get_db
from app.schemas.auth import LoginRequest, Token, RefreshRequest, LogoutRequest
from app.schemas.user import UserRead
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
auth_service = AuthService()

@router.post("/login", response_model=Token)
def login(data: LoginRequest, db: Session = Depends(get_db)):
    user = auth_service.authenticate(db, data.username, data.password)
    if not user:
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
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }

@router.post("/refresh", response_model=Token)
def refresh(data: RefreshRequest, db: Session = Depends(get_db)):
    try:
        tokens = auth_service.refresh_tokens(db, data.refresh_token)
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from exc
    return {
        "access_token": tokens["access_token"],
        "refresh_token": tokens["refresh_token"],
        "token_type": "bearer",
    }

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(data: LogoutRequest, db: Session = Depends(get_db)):
    auth_service.logout(db, data.refresh_token)

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: UserRead = Depends(get_current_user)):
    return current_user
