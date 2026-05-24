from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.schemas.archive_entry import ArchiveEntryRead
from app.services.search import SearchService

router = APIRouter(prefix="/search", tags=["search"])
service = SearchService()


@router.get("/", response_model=list[ArchiveEntryRead])
def search_archive_entries(
    q: str | None = None,
    genre: str | None = None,
    tag: str | None = None,
    developer: str | None = None,
    publisher: str | None = None,
    franchise: str | None = None,
    metadata_status: str | None = None,
    verification_status: str | None = None,
    storage_device: str | None = None,
    offset: int = 0,
    limit: int = 100,
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
