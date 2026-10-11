from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.core.access import acting_as
from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.models.franchise import Franchise
from app.schemas.franchise import FranchiseCreate, FranchiseImageSource, FranchiseRead, FranchiseUpdate
from app.services.audit import AuditService
from app.services.franchise import FranchiseService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/franchises", tags=["franchises"])
service = FranchiseService()
audit_service = AuditService()


@router.get(
    "/",
    response_model=list[FranchiseRead],
    summary="List franchises",
    description="Return franchises with pagination.",
    response_description="Franchises retrieved.",
)
def list_franchises(
    response: Response,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
    q: str | None = None,
):
    items = service.list_items(db, offset=offset, limit=limit, q=q, viewer=current_user)
    response.headers["X-Total-Count"] = str(service.count(db, q=q, viewer=current_user))
    return items


@router.get(
    "/{franchise_id}",
    response_model=FranchiseRead,
    summary="Get franchise",
    description="Return a single franchise by ID.",
    response_description="Franchise retrieved.",
)
def read_franchise(
    franchise_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id, current_user)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    return franchise


@router.post(
    "/",
    response_model=FranchiseRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create franchise",
    description="Create a new franchise record.",
    response_description="Franchise created.",
)
def create_franchise(
    data: FranchiseCreate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    if service.repo.get_by_name(db, data.name):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Franchise name already exists")
    franchise = service.create(db, data)
    audit_service.record(
        db,
        current_user,
        action="create",
        entity="Franchise",
        entity_id=franchise.id,
        details=f"Created franchise {franchise.name}",
    )
    return franchise


@router.patch(
    "/{franchise_id}",
    response_model=FranchiseRead,
    summary="Update franchise",
    description="Update a franchise record.",
    response_description="Franchise updated.",
)
def update_franchise(
    franchise_id: str,
    data: FranchiseUpdate,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    updated = service.update(db, franchise, data)
    audit_service.record(
        db,
        current_user,
        action="update",
        entity="Franchise",
        entity_id=updated.id,
        details=f"Updated franchise {updated.name}",
    )
    return updated


@router.delete(
    "/{franchise_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete franchise",
    description="Soft delete a franchise by ID.",
    response_description="Franchise deleted.",
)
def delete_franchise(
    franchise_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    service.delete(db, franchise)
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Franchise",
        entity_id=franchise.id,
        details=f"Deleted franchise {franchise.name}",
    )


def _editable(db: Session, franchise_id: str) -> Franchise:
    franchise = service.get(db, franchise_id)
    if franchise is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Franchise not found")
    return franchise


def _image_changed(db: Session, current_user, franchise: Franchise, details: str) -> Franchise:
    audit_service.record(db, current_user, action="update", entity="Franchise", entity_id=franchise.id, details=details)
    return service.get(db, franchise.id, current_user)


@router.get(
    "/{franchise_id}/image-candidates",
    response_model=list[str],
    summary="List franchise image candidates",
    description="Wide images to choose from: the franchise's games' banners, SteamGridDB art for a game of the same name, then the games' screenshots. Stored paths are relative to the media root; the rest are URLs.",
    response_description="Candidate images, best first.",
)
def list_franchise_image_candidates(
    franchise_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = _editable(db, franchise_id)
    with acting_as(current_user.id):
        return service.image_candidates(db, franchise, current_user)


@router.put(
    "/{franchise_id}/image",
    response_model=FranchiseRead,
    summary="Choose franchise image",
    description="Copy one of the offered candidates in as the franchise's image.",
    response_description="Franchise updated.",
)
def choose_franchise_image(
    franchise_id: str,
    data: FranchiseImageSource,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = _editable(db, franchise_id)
    try:
        with acting_as(current_user.id):
            service.set_image(db, franchise, data.source, current_user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _image_changed(db, current_user, franchise, f"Chose an image for franchise {franchise.name}")


@router.post(
    "/{franchise_id}/image",
    response_model=FranchiseRead,
    summary="Upload franchise image",
    description="Upload an image for the franchise. Accepts multipart form data.",
    response_description="Franchise updated.",
)
def upload_franchise_image(
    franchise_id: str,
    file: UploadFile = File(..., description="Image file"),
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = _editable(db, franchise_id)
    try:
        service.upload_image(db, franchise, file)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return _image_changed(db, current_user, franchise, f"Uploaded an image for franchise {franchise.name}")


@router.delete(
    "/{franchise_id}/image",
    response_model=FranchiseRead,
    summary="Reset franchise image",
    description="Remove the chosen image; the franchise shows one of its games' banners again.",
    response_description="Franchise updated.",
)
def reset_franchise_image(
    franchise_id: str,
    current_user=Depends(require_permission(PermissionName.EDIT_METADATA)),
    db: Session = Depends(get_db),
):
    franchise = _editable(db, franchise_id)
    service.clear_image(db, franchise)
    return _image_changed(db, current_user, franchise, f"Reset the image of franchise {franchise.name}")
