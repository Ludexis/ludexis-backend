"""version_grouping
Revision ID: 3b7d9e1c2a40
Revises: ecabaf1d5dab
Create Date: 2026-10-06 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '3b7d9e1c2a40'
down_revision = 'ecabaf1d5dab'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('archive_entries', sa.Column('group_key', sa.String(length=256), nullable=True))
    op.add_column('archive_entries', sa.Column('series_key', sa.String(length=256), nullable=True))
    op.add_column('archive_entries', sa.Column('episode', sa.Integer(), nullable=True))
    op.add_column('archive_entries', sa.Column('season', sa.Integer(), nullable=True))
    op.add_column('archive_entries', sa.Column('is_primary_version', sa.Boolean(), server_default=sa.true(), nullable=False))
    op.create_index(op.f('ix_archive_entries_group_key'), 'archive_entries', ['group_key'], unique=False)
    op.create_index(op.f('ix_archive_entries_series_key'), 'archive_entries', ['series_key'], unique=False)
    op.add_column('collections', sa.Column('auto_key', sa.String(length=256), nullable=True))
    op.create_unique_constraint('collections_auto_key_key', 'collections', ['auto_key'])


def downgrade() -> None:
    op.drop_constraint('collections_auto_key_key', 'collections', type_='unique')
    op.drop_column('collections', 'auto_key')
    op.drop_index(op.f('ix_archive_entries_series_key'), table_name='archive_entries')
    op.drop_index(op.f('ix_archive_entries_group_key'), table_name='archive_entries')
    op.drop_column('archive_entries', 'is_primary_version')
    op.drop_column('archive_entries', 'season')
    op.drop_column('archive_entries', 'episode')
    op.drop_column('archive_entries', 'series_key')
    op.drop_column('archive_entries', 'group_key')
