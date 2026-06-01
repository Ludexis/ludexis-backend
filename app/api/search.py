from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.schemas.archive_entry import ArchiveEntryRead
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])
service = SearchService()


@router.get(
    "/",
    response_model=list[ArchiveEntryRead],
    summary="Search archive entries",
    description="Search archive entries by text and filters.",
    response_description="Search results retrieved.",
)
def search_archive_entries(
    q: str | None = Query(None, description="Text query", example="space adventure"),
    genre: str | None = Query(None, description="Genre filter", example="RPG"),
    tag: str | None = Query(None, description="Tag filter", example="retro"),
    developer: str | None = Query(None, description="Developer filter", example="Studio Polaris"),
    publisher: str | None = Query(None, description="Publisher filter", example="Orbit Publishing"),
    franchise: str | None = Query(None, description="Franchise filter", example="Skybound Saga"),
    metadata_status: str | None = Query(None, description="Metadata status filter", example="MATCHED"),
    verification_status: str | None = Query(None, description="Verification status filter", example="VERIFIED"),
    storage_device: str | None = Query(None, description="Storage device filter", example="NAS-01"),
    offset: int = Query(0, description="Pagination offset", example=0),
    limit: int = Query(100, description="Pagination limit", example=100),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return service.search(
        db,
        query=q,
        genre=genre,
        tag=tag,
        developer=developer,
        publisher=publisher,
        franchise=franchise,
        metadata_status=metadata_status,
        verification_status=verification_status,
        storage_device=storage_device,
        offset=offset,
        limit=limit,
    )
