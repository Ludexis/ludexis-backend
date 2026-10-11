"""user_restricted_only
Revision ID: a3c9e5f17b42
Revises: e9b4d7a2c613
Create Date: 2026-10-11 16:30:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'a3c9e5f17b42'
down_revision = 'e9b4d7a2c613'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('restricted_only', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('users', 'restricted_only')
