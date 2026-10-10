"""drop_unused_tables
Revision ID: e9b4d7a2c613
Revises: c3e8a1d5f924
Create Date: 2026-10-11 12:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = 'e9b4d7a2c613'
down_revision = 'c3e8a1d5f924'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Notes, ratings and the metadata source registry were never wired to any API or screen.
    op.drop_table('ratings')
    op.drop_table('notes')
    op.drop_column('archive_entries', 'metadata_source_id')
    op.drop_table('metadata_sources')


def downgrade() -> None:
    op.create_table('metadata_sources',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('provider_name', sa.String(length=128), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('provider_name')
    )
    op.add_column('archive_entries', sa.Column('metadata_source_id', sa.String(length=36), nullable=True))
    op.create_foreign_key(None, 'archive_entries', 'metadata_sources', ['metadata_source_id'], ['id'], ondelete='SET NULL')
    for table, extra in (
        ('notes', [sa.Column('content', sa.Text(), nullable=False)]),
        ('ratings', [sa.Column('score', sa.Integer(), nullable=False), sa.Column('review', sa.Text(), nullable=True)]),
    ):
        op.create_table(table,
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('archive_entry_id', sa.String(length=36), nullable=False),
        *extra,
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['archive_entry_id'], ['archive_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
        )
