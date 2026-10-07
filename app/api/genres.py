from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.db.session import get_db
from app.repositories.genre import GenreRepository
from app.schemas.genre import GenreRead

router = APIRouter(prefix="/genres", tags=["genres"])
genre_repo = GenreRepository()


@router.get(
    "/",
    response_model=list[GenreRead],
    summary="List genres",
    description="Return every genre that has at least one entry, with its entry count.",
    response_description="Genres retrieved.",
)
def list_genres(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    return [GenreRead(name=name, entry_count=count) for name, count in genre_repo.list_with_counts(db)]
