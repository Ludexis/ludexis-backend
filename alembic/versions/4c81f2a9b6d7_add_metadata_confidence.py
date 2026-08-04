"""add metadata_confidence to archive_entries

Revision ID: 4c81f2a9b6d7
Revises: fea948af07c9
Create Date: 2026-08-04 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4c81f2a9b6d7'
down_revision = 'fea948af07c9'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'archive_entries',
        sa.Column('metadata_confidence', sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('archive_entries', 'metadata_confidence')
