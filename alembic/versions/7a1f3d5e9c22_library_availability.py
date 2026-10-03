"""library_availability
Revision ID: 7a1f3d5e9c22
Revises: 5c2e8f4a6b13
Create Date: 2026-10-06 14:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = '7a1f3d5e9c22'
down_revision = '5c2e8f4a6b13'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('libraries', sa.Column('status', sa.String(length=16), server_default='ONLINE', nullable=False))
    op.add_column('libraries', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('libraries', sa.Column('last_scan_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('libraries', sa.Column('last_error', sa.Text(), nullable=True))
    op.add_column('archive_entries', sa.Column('relative_path', sa.Text(), nullable=True))
    op.create_index('ix_archive_entries_library_relative_path', 'archive_entries', ['library_id', 'relative_path'], unique=False)
    # Entries under their library root get their relative path now; the next scan fills in the rest.
    op.execute(
        """
        UPDATE archive_entries AS e
        SET relative_path = replace(substr(e.file_path, length(rtrim(l.path, '/\\')) + 2), '\\', '/')
        FROM libraries AS l
        WHERE e.library_id = l.id
          AND starts_with(e.file_path, rtrim(l.path, '/\\'))
          AND length(e.file_path) > length(rtrim(l.path, '/\\')) + 1
        """
    )


def downgrade() -> None:
    op.drop_index('ix_archive_entries_library_relative_path', table_name='archive_entries')
    op.drop_column('archive_entries', 'relative_path')
    op.drop_column('libraries', 'last_error')
    op.drop_column('libraries', 'last_scan_at')
    op.drop_column('libraries', 'last_seen_at')
    op.drop_column('libraries', 'status')
