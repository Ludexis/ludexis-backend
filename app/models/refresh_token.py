import uuid

import sqlalchemy as sa
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import Base


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: str = mapped_column(sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    token: str = mapped_column(sa.Text, nullable=False, unique=True)
    user_id = mapped_column(sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    expires_at = mapped_column(sa.DateTime(timezone=True), nullable=False)
    revoked: bool = mapped_column(sa.Boolean, default=False, nullable=False)
    created_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)
    updated_at = mapped_column(sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False)

    user = relationship("User", back_populates="refresh_tokens")
