from fastapi import APIRouter, Depends, HTTPException

from app.core.auth import get_current_active_user
from app.core.dependencies import get_metadata_service
from app.schemas.metadata import MetadataDetails, MetadataSearchResult
from app.services.metadata import MetadataService

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get("/search", response_model=list[MetadataSearchResult])
def search_metadata(
    q: str,
    provider_priority: list[str] | None = None,
    current_user=Depends(get_current_active_user),
    metadata_service: MetadataService = Depends(get_metadata_service),
):
    return metadata_service.search(q, preferred_providers=provider_priority)


@router.get("/details/{provider_name}/{provider_id}", response_model=MetadataDetails)
def read_metadata_details(
    provider_name: str,
    provider_id: str,
    current_user=Depends(get_current_active_user),
    metadata_service: MetadataService = Depends(get_metadata_service),
):
    details = metadata_service.get_details(provider_name, provider_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Metadata not found")
    return details


@router.get("/artwork/{provider_name}/{provider_id}")
def read_metadata_artwork(
    provider_name: str,
    provider_id: str,
    current_user=Depends(get_current_active_user),
    metadata_service: MetadataService = Depends(get_metadata_service),
):
    artwork = metadata_service.download_artwork(provider_name, provider_id)
    if artwork is None:
        raise HTTPException(status_code=404, detail="Artwork not available")
    return artwork
