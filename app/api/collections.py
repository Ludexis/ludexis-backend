from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.collection import CollectionCreate, CollectionEntryRequest, CollectionRead, CollectionUpdate
from app.services.collection import CollectionService
from app.utils.enums import PermissionName
from app.schemas.collection import CollectionCreate, CollectionEntryRequest, CollectionRead, CollectionUpdate
from app.services.collection import CollectionService

router = APIRouter(prefix="/collections", tags=["collections"])
service = CollectionService()


@router.get("/", response_model=list[CollectionRead])
def list_collections(
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
    offset: int = 0,
    limit: int = 100,
):
    return service.list(db, offset=offset, limit=limit)


@router.get("/{collection_id}", response_model=CollectionRead)
def read_collection(
    collection_id: str,
    current_user=Depends(get_current_active_user),
    db: Session = Depends(get_db),
):
    collection = service.get(db, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    return collection


@router.post("/", response_model=CollectionRead, status_code=status.HTTP_201_CREATED)
def create_collection(
    data: CollectionCreate,
    current_user=Depends(require_permission(PermissionName.MANAGE_COLLECTIONS)),
    db: Session = Depends(get_db),
):
    try:
        return service.create(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.patch("/{collection_id}", response_model=CollectionRead)
def update_collection(
    collection_id: str,
    data: CollectionUpdate,
    current_user=Depends(require_permission(PermissionName.MANAGE_COLLECTIONS)),
    db: Session = Depends(get_db),
):
    collection = service.get(db, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    try:
        return service.update(db, collection, data)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{collection_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_collection(
    collection_id: str,
    current_user=Depends(require_permission(PermissionName.MANAGE_COLLECTIONS)),
    db: Session = Depends(get_db),
):
    collection = service.get(db, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    service.delete(db, collection)


@router.post("/{collection_id}/entries", response_model=CollectionRead)
def add_entry_to_collection(
    collection_id: str,
    data: CollectionEntryRequest,
    current_user=Depends(require_permission(PermissionName.MANAGE_COLLECTIONS)),
    db: Session = Depends(get_db),
):
    collection = service.get(db, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    try:
        return service.add_entry(db, collection, data.entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.delete("/{collection_id}/entries/{entry_id}", response_model=CollectionRead)
def remove_entry_from_collection(
    collection_id: str,
    entry_id: str,
    current_user=Depends(require_permission(PermissionName.MANAGE_COLLECTIONS)),
    db: Session = Depends(get_db),
):
    collection = service.get(db, collection_id)
    if collection is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Collection not found")
    try:
        return service.remove_entry(db, collection, entry_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
