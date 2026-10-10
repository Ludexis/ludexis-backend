"""hash_refresh_tokens
Revision ID: c3e8a1d5f924
Revises: a6c9e2f4b871
Create Date: 2026-10-11 11:00:00.000000
"""

import hashlib

from alembic import op
import sqlalchemy as sa


revision = 'c3e8a1d5f924'
down_revision = 'a6c9e2f4b871'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Stored tokens become their SHA-256 digest; sessions keep working because lookups hash the presented token.
    bind = op.get_bind()
    for token_id, token in bind.execute(sa.text("SELECT id, token FROM refresh_tokens")).all():
        digest = hashlib.sha256(token.encode()).hexdigest()
        bind.execute(sa.text("UPDATE refresh_tokens SET token = :digest WHERE id = :id"), {"digest": digest, "id": token_id})


def downgrade() -> None:
    # Digests cannot be turned back into tokens; the sessions they belonged to end.
    op.execute("UPDATE refresh_tokens SET revoked = true")
