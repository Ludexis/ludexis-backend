"""user_sessions_revoked_at
Revision ID: d8f3a1c6e297
Revises: b2e7c4a9d156
Create Date: 2026-10-07 11:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'd8f3a1c6e297'
down_revision = 'b2e7c4a9d156'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('sessions_revoked_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'sessions_revoked_at')
