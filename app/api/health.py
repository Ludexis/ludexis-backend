from fastapi import APIRouter, Depends, HTTPException
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import get_db

logger = get_logger(__name__)

router = APIRouter(
    prefix="/health",
    tags=["health"],
)


@router.get("/")
def health():
    return {"status": "healthy"}


@router.get("/db")
def database_health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"database": "healthy"}

    except Exception as exc:
        logger.warning("Database health check failed: %s", exc)
        raise HTTPException(status_code=503, detail={"database": "unhealthy"}) from exc


@router.get("/redis")
def redis_health():
    try:
        redis_client = Redis.from_url(
            str(settings.REDIS_URL)
        )
        redis_client.ping()

        return {"redis": "healthy"}

    except Exception as exc:
        logger.warning("Redis health check failed: %s", exc)
        raise HTTPException(status_code=503, detail={"redis": "unhealthy"}) from exc