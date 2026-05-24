from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_active_user, require_permission
from app.db.session import get_db
from app.schemas.collection import CollectionCreate, CollectionEntryRequest, CollectionRead, CollectionUpdate
from app.services.audit import AuditService
from app.services.collection import CollectionService
from app.utils.enums import PermissionName

router = APIRouter(prefix="/collections", tags=["collections"])
service = CollectionService()
audit_service = AuditService()


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
        collection = service.create(db, data)
        audit_service.record(
            db,
            current_user,
            action="create",
            entity="Collection",
            entity_id=collection.id,
            details=f"Created collection {collection.name}",
        )
        return collection
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
        updated = service.update(db, collection, data)
        audit_service.record(
            db,
            current_user,
            action="update",
            entity="Collection",
            entity_id=updated.id,
            details=f"Updated collection {updated.name}",
        )
        return updated
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
    audit_service.record(
        db,
        current_user,
        action="delete",
        entity="Collection",
        entity_id=collection.id,
        details=f"Deleted collection {collection.name}",
    )


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
        updated = service.add_entry(db, collection, data.entry_id)
        audit_service.record(
            db,
            current_user,
            action="update",
            entity="Collection",
            entity_id=updated.id,
            details=f"Added entry {data.entry_id} to collection {updated.name}",
        )
        return updated
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
        updated = service.remove_entry(db, collection, entry_id)
        audit_service.record(
            db,
            current_user,
            action="update",
            entity="Collection",
            entity_id=updated.id,
            details=f"Removed entry {entry_id} from collection {updated.name}",
        )
        return updated
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
