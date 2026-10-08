"""archive_review_resolved
Revision ID: e4a7c2b9d358
Revises: d8f3a1c6e297
Create Date: 2026-10-09 10:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'e4a7c2b9d358'
down_revision = 'd8f3a1c6e297'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('archive_entries', sa.Column('review_resolved', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    op.drop_column('archive_entries', 'review_resolved')
