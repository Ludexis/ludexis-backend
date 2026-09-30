from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy.orm import Session

from app.api import api_router
from jose import JWTError

from app.core.auth import get_current_active_user, get_current_user, oauth2_scheme_optional
from app.core.security import verify_token
from app.repositories.user import UserRepository
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine, get_db
from app.services.storage import StorageService

setup_logging()

app = FastAPI(
    title="Ludexis Backend",
    version="0.1.0",
    description="Self-hosted game archive metadata catalog backend built with FastAPI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
    expose_headers=["X-Total-Count"],
)

app.include_router(api_router)

media_dir = StorageService().base_dir
media_dir.mkdir(parents=True, exist_ok=True)

media_router = APIRouter()


def get_media_user(
    token: str | None = Depends(oauth2_scheme_optional),
    media_token: str | None = None,
    db: Session = Depends(get_db),
):
    if token:
        return get_current_active_user(get_current_user(token, db))
    # <img> tags cannot send an Authorization header, so they pass a media-only token (GET /api/auth/media-token).
    if not media_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    try:
        user = UserRepository().get(db, verify_token(media_token, token_type="media"))
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid media token") from exc
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    return user


@media_router.get("/media/{path:path}")
def read_media(path: str, current_user=Depends(get_media_user)):
    requested_path = (media_dir / path).resolve()
    if requested_path != media_dir and media_dir not in requested_path.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    if not requested_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return FileResponse(requested_path)


app.include_router(media_router)

Instrumentator().instrument(app).expose(
    app,
    endpoint="/api/metrics",
)

@app.get("/healthz", summary="Health check")
def health_check():
    return {"status": "ok"}
