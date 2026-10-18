import hashlib
import secrets

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.edge_device import EdgeDevice

TOKEN_PREFIX = "ldx_"


def new_edge_token() -> str:
    return TOKEN_PREFIX + secrets.token_urlsafe(32)


def hash_edge_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def get_current_edge(request: Request, db: Session = Depends(get_db)) -> EdgeDevice:
    """An edge device authenticates with its own token; user sessions and cookies are not accepted here."""
    scheme, _, token = request.headers.get("Authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token.startswith(TOKEN_PREFIX):
        raise HTTPException(status_code=401, detail="Edge token required", headers={"WWW-Authenticate": "Bearer"})
    edge = db.query(EdgeDevice).filter(EdgeDevice.token_hash == hash_edge_token(token)).one_or_none()
    if edge is None:
        raise HTTPException(status_code=401, detail="Unknown or revoked edge token", headers={"WWW-Authenticate": "Bearer"})
    return edge
