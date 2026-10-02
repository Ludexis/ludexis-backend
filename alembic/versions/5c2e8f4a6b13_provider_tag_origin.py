"""provider_tag_origin
Revision ID: 5c2e8f4a6b13
Revises: 3b7d9e1c2a40
Create Date: 2026-10-06 13:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '5c2e8f4a6b13'
down_revision = '3b7d9e1c2a40'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tags', sa.Column('origin', sa.String(length=16), server_default='user', nullable=False))


def downgrade() -> None:
    op.drop_column('tags', 'origin')
