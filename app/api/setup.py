from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.repositories.user import UserRepository

router = APIRouter(prefix="/setup", tags=["setup"])
user_repo = UserRepository()


@router.get(
    "/status",
    summary="Get setup status",
    description="Return whether the system has been initialized and whether the default administrator still has its first-run password.",
    response_description="Setup status retrieved.",
)
def setup_status(db: Session = Depends(get_db)):
    # The default administrator is created on first start; until its password is changed the sign-in page names it.
    admin = user_repo.get_by_username(db, settings.DEFAULT_ADMIN_USERNAME)
    default_login = admin.username if admin is not None and admin.must_change_password else None
    return {"initialized": user_repo.has_any(db), "default_login": default_login}
