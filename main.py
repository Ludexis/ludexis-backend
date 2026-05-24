from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.core.config import settings
from app.core.logging import setup_logging
from app.db.session import engine
from app.db.base import Base

setup_logging()

Base.metadata.create_all(bind=engine)

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

@app.get("/healthz", summary="Health check")
def health_check():
    return {"status": "ok"}
