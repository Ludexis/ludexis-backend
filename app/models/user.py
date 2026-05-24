import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base
from app.models.association_tables import user_roles


class User(Base):
    __tablename__ = "users"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: str = mapped_column(sa.String(128), unique=True, nullable=False)
    email: str = mapped_column(sa.String(256), unique=True, nullable=False)
    hashed_password: str = mapped_column(sa.String(256), nullable=False)
    is_active: bool = mapped_column(sa.Boolean, default=True, nullable=False)
    is_superuser: bool = mapped_column(sa.Boolean, default=False, nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)
    deleted_at = mapped_column(sa.DateTime(timezone=True), nullable=True)

    roles = relationship("Role", secondary=user_roles, backref="users")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    notes = relationship("Note", back_populates="user", cascade="all, delete-orphan")
    ratings = relationship("Rating", back_populates="user", cascade="all, delete-orphan")
