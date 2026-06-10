from fastapi import APIRouter
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import Depends
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends

from app.core.config import settings
from app.db.session import get_db


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
        return {"database": "unhealthy", "error": str(exc)}
    
    
@router.get("/redis")
def redis_health():
    try:
        redis_client = Redis.from_url(str(settings.REDIS_URL))
        redis_client.ping()
        return {"redis": "healthy"}

    except Exception as exc:
        return {"redis": "unhealthy", "error": str(exc)}