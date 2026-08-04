from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.services.storage import StorageService

setup_logging()

app = FastAPI(
    title="Ludexis Backend",
    version="0.1.0",
    description="Self-hosted game archive metadata catalog backend built with FastAPI.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True,
)

app.include_router(api_router)

media_dir = StorageService().base_dir
media_dir.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=str(media_dir)), name="media")

Instrumentator().instrument(app).expose(
    app,
    endpoint="/api/metrics",
)

@app.get("/healthz", summary="Health check")
def health_check():
    return {"status": "ok"}
