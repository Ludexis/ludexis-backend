from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.schemas.archive_entry import ArchiveEntryRead
from app.core.access import annotate_flags
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
    response: Response,
    q: str | None = Query(None, description="Text query", examples=["space adventure"]),
    genre: str | None = Query(None, description="Genre filter", examples=["RPG"]),
    tag: str | None = Query(None, description="Tag filter", examples=["retro"]),
    developer: str | None = Query(None, description="Developer filter", examples=["Studio Polaris"]),
    publisher: str | None = Query(None, description="Publisher filter", examples=["Orbit Publishing"]),
    franchise: str | None = Query(None, description="Franchise filter", examples=["Skybound Saga"]),
    collection: str | None = Query(None, description="Collection name filter", examples=["Classics"]),
    collection_id: str | None = Query(None, description="Collection id filter (names are not unique)"),
    metadata_status: str | None = Query(None, description="Metadata status filter", examples=["MATCHED"]),
    verification_status: str | None = Query(None, description="Verification status filter", examples=["VERIFIED"]),
    storage_device: str | None = Query(None, description="Storage device filter", examples=["NAS-01"]),
    group_versions: bool = Query(False, description="Return one entry per game, with version_count set"),
    favorite: bool | None = Query(None, description="Only games the current user marked favourite (true) or did not (false)"),
    completed: bool | None = Query(None, description="Only games the current user marked completed (true) or did not (false)"),
    review_resolved: bool | None = Query(None, description="Only games dismissed from (true) or still in (false) the review queue"),
    sort: str = Query(
        "title",
        pattern="^-?(title|created_at|release_date|file_size|random)$",
        description="Sort field; prefix with - for descending",
        examples=["-created_at"],
    ),
    offset: int = Query(0, description="Pagination offset", examples=[0]),
    limit: int = Query(100, description="Pagination limit", examples=[100]),
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    filters = dict(
        query=q,
        genre=genre,
        tag=tag,
        developer=developer,
        publisher=publisher,
        franchise=franchise,
        collection=collection,
        collection_id=collection_id,
        metadata_status=metadata_status,
        verification_status=verification_status,
        storage_device=storage_device,
        group_versions=group_versions,
        review_resolved=review_resolved,
        viewer=current_user,
        favorite=favorite,
        completed=completed,
    )
    response.headers["X-Total-Count"] = str(service.count(db, **filters))
    return annotate_flags(db, current_user, service.search(db, sort=sort, offset=offset, limit=limit, **filters))
