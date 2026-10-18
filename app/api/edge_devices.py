from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.auth import require_permission
from app.db.session import get_db
from app.models.edge_device import EdgeDevice
from app.schemas.edge import EdgeBundleRequest, EdgeDeviceCreate, EdgeDeviceCreated, EdgeDeviceRead, EdgeDeviceUpdate
from app.services.audit import AuditService
from app.services.edge import EdgeService
from app.utils.audit_actions import AuditAction
from app.utils.enums import PermissionName

router = APIRouter(prefix="/edge-devices", tags=["edge devices"])
service = EdgeService()
audit = AuditService()
admin = require_permission(PermissionName.ACCESS_ADMIN)


def _edge(db: Session, edge_id: str) -> EdgeDevice:
    edge = db.get(EdgeDevice, edge_id)
    if edge is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Edge device not found")
    return edge


@router.get("/", response_model=list[EdgeDeviceRead], summary="List edge devices", description="Edge devices with their status, drives and libraries.")
def list_edge_devices(current_user=Depends(admin), db: Session = Depends(get_db)):
    return [service.read(db, edge) for edge in service.list_devices(db)]


@router.post(
    "/",
    response_model=EdgeDeviceCreated,
    status_code=status.HTTP_201_CREATED,
    summary="Add edge device",
    description="Register a device; the response holds its token, which is not shown again.",
)
def create_edge_device(data: EdgeDeviceCreate, current_user=Depends(admin), db: Session = Depends(get_db)):
    try:
        edge, token = service.create(db, data.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit.log(db, action=AuditAction.CREATE_EDGE_DEVICE, entity="EdgeDevice", entity_id=edge.id, user_id=current_user.id, details=f"Added edge device '{edge.name}'")
    return {**service.read(db, edge), "token": token}


@router.patch("/{edge_id}", response_model=EdgeDeviceRead, summary="Update edge device", description="Rename a device or change its scan and metadata settings.")
def update_edge_device(edge_id: str, data: EdgeDeviceUpdate, current_user=Depends(admin), db: Session = Depends(get_db)):
    edge = _edge(db, edge_id)
    try:
        edge = service.update(db, edge, data.model_dump(exclude_none=True))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    audit.log(db, action=AuditAction.UPDATE_EDGE_DEVICE, entity="EdgeDevice", entity_id=edge.id, user_id=current_user.id, details=f"Updated edge device '{edge.name}'")
    return service.read(db, edge)


@router.delete(
    "/{edge_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove edge device",
    description="Revoke the device; its libraries and entries stay and show as offline.",
)
def delete_edge_device(edge_id: str, current_user=Depends(admin), db: Session = Depends(get_db)):
    edge = _edge(db, edge_id)
    name = edge.name
    service.delete(db, edge)
    audit.log(db, action=AuditAction.DELETE_EDGE_DEVICE, entity="EdgeDevice", entity_id=edge_id, user_id=current_user.id, details=f"Removed edge device '{name}'")


@router.post("/{edge_id}/token", response_model=EdgeDeviceCreated, summary="Rotate edge token", description="Issue a new token; the old one stops working at once.")
def rotate_edge_token(edge_id: str, current_user=Depends(admin), db: Session = Depends(get_db)):
    edge = _edge(db, edge_id)
    token = service.rotate_token(db, edge)
    audit.log(db, action=AuditAction.ROTATE_EDGE_TOKEN, entity="EdgeDevice", entity_id=edge.id, user_id=current_user.id, details=f"Rotated the token of edge device '{edge.name}'")
    return {**service.read(db, edge), "token": token}


@router.post(
    "/{edge_id}/bundle",
    summary="Download edge bundle",
    description="A zip with the compose file, .env and installer for Linux or Windows; needs the device's current token.",
    response_class=Response,
)
def download_edge_bundle(edge_id: str, data: EdgeBundleRequest, request: Request, current_user=Depends(admin), db: Session = Depends(get_db)):
    edge = _edge(db, edge_id)
    if not service.token_matches(edge, data.token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="That is not this device's current token")
    content = service.bundle(edge, data.os, data.token, str(request.base_url))
    return Response(
        content,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="ludexis-edge-{data.os}.zip"', "Cache-Control": "no-store"},
    )
