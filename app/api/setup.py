from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.session import get_db
from app.repositories.user import UserRepository
from app.schemas.user import UserCreate, UserRead

router = APIRouter(prefix="/setup", tags=["setup"])
user_repo = UserRepository()


@router.get("/status")
def setup_status(db: Session = Depends(get_db)):
    initialized = user_repo.has_any(db)
    return {"initialized": initialized}


@router.post("/initialize", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def initialize_system(data: UserCreate, db: Session = Depends(get_db)):
    if user_repo.has_any(db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="System already initialized")

    if user_repo.get_by_username(db, data.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username is already in use",
        )
    if user_repo.get_by_email(db, data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already in use",
        )

    hashed_password = hash_password(data.password)
    user = user_repo.create(db, {
        "username": data.username,
        "email": data.email,
        "hashed_password": hashed_password,
        "is_active": True,
        "is_superuser": True,
    })

    return user
