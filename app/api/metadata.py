from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user
from app.core.dependencies import get_metadata_service
from app.db.session import get_db
from app.providers.notices import get_notices
from app.schemas.metadata import MetadataDetails, MetadataSearchResult, ProviderNotice
from app.core.access import acting_as, restricted_providers, restricted_sources_allowed
from app.services.metadata import MetadataService
from app.services.settings import SettingsService

router = APIRouter(prefix="/metadata", tags=["metadata"])


@router.get(
    "/search",
    response_model=list[MetadataSearchResult],
    summary="Search metadata providers",
    description="Search configured metadata providers for a query.",
    response_description="Metadata search results retrieved.",
)
def search_metadata(
    q: str = Query(..., description="Search query", examples=["Star Explorer"]),
    provider_priority: list[str] | None = Query(
        None,
        description="Preferred provider order",
        examples=["igdb", "steam"],
    ),
    provider: str | None = Query(
        None,
        description='Search only this provider, or "all" for every enabled provider; results include cover thumbnails.',
        examples=["VNDB", "all"],
    ),
    developer: str | None = Query(
        None,
        max_length=256,
        description="Optional developer name; with a provider, that developer's games are searched too and listed first.",
        examples=["Example Studio"],
    ),
    current_user=Depends(get_current_active_user),
    metadata_service: MetadataService = Depends(get_metadata_service),
    db: Session = Depends(get_db),
):
    with acting_as(current_user.id):
        if provider:
            return metadata_service.search_providers(db, q, provider, developer=developer.strip() if developer else None)
        return metadata_service.search(q, preferred_providers=provider_priority, allowed=SettingsService().match_providers(db))


@router.get(
    "/providers",
    response_model=list[str],
    summary="List match providers",
    description="Providers interactive search and auto-matching use, in their configured order.",
    response_description="Enabled provider names.",
)
def list_match_providers(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    with acting_as(current_user.id):
        return SettingsService().match_providers(db)


@router.get(
    "/notices",
    response_model=list[ProviderNotice],
    summary="List provider notices",
    description="Current warnings from the enabled providers this account may use, such as an expired sign-in or a reached rate limit.",
    response_description="Provider notices.",
)
def list_provider_notices(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    with acting_as(current_user.id):
        return get_notices(SettingsService().match_providers(db))


@router.get(
    "/details/{provider_name}/{provider_id}",
    response_model=MetadataDetails,
    summary="Get metadata details",
    description="Fetch detailed metadata for a provider entry.",
    response_description="Metadata details retrieved.",
)
def read_metadata_details(
    provider_name: str,
    provider_id: str,
    current_user=Depends(get_current_active_user),
    metadata_service: MetadataService = Depends(get_metadata_service),
    db: Session = Depends(get_db),
):
    with acting_as(current_user.id):
        if provider_name in restricted_providers() and not restricted_sources_allowed(db):
            raise HTTPException(status_code=404, detail="Metadata not found")
    details = metadata_service.get_details(provider_name, provider_id)
    if details is None:
        raise HTTPException(status_code=404, detail="Metadata not found")
    return details
