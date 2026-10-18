from contextlib import asynccontextmanager

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from prometheus_fastapi_instrumentator import Instrumentator

from app import __version__
from app.api import api_router

from app.core.access import media_visible
from app.core.auth import get_current_active_user
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import SessionLocal, get_db
from app.services.bootstrap import ensure_default_admin
from app.services.storage import StorageService
from app.utils.artwork import is_versioned

setup_logging()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # A fresh server gets the default administrator, so the first sign-in needs no extra setup step.
    with SessionLocal() as db:
        ensure_default_admin(db)
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Ludexis Backend",
    version=__version__,
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


@media_router.get("/media/{path:path}")
def read_media(path: str, current_user=Depends(get_current_active_user), db: Session = Depends(get_db)):
    requested_path = (media_dir / path).resolve()
    if requested_path != media_dir and media_dir not in requested_path.parents:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # Art of games the user may not see is as absent as the games themselves.
    if not requested_path.is_file() or not media_visible(db, current_user, path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    # A versioned name never changes contents, so the browser keeps it; older names are revalidated (a cheap 304) on every use.
    cache = "private, max-age=31536000, immutable" if is_versioned(path) else "private, no-cache"
    return FileResponse(requested_path, headers={"Cache-Control": cache})


app.include_router(media_router)

Instrumentator().instrument(app).expose(
    app,
    endpoint="/api/metrics",
)

@app.get("/healthz", summary="Health check")
def health_check():
    return {"status": "ok"}
