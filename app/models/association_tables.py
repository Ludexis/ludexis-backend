import sqlalchemy as sa
from sqlalchemy import Table

from app.db.base import Base
from app.utils.enums import PermissionName, RelationshipType

archive_entry_genres = Table(
    "archive_entry_genres",
    Base.metadata,
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("genre_id", sa.ForeignKey("genres.id", ondelete="CASCADE"), primary_key=True),
)

archive_entry_tags = Table(
    "archive_entry_tags",
    Base.metadata,
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("tag_id", sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)

archive_entry_developers = Table(
    "archive_entry_developers",
    Base.metadata,
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("developer_id", sa.ForeignKey("developers.id", ondelete="CASCADE"), primary_key=True),
)

archive_entry_publishers = Table(
    "archive_entry_publishers",
    Base.metadata,
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("publisher_id", sa.ForeignKey("publishers.id", ondelete="CASCADE"), primary_key=True),
)

collection_entries = Table(
    "collection_entries",
    Base.metadata,
    sa.Column("collection_id", sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
)

franchise_entries = Table(
    "franchise_entries",
    Base.metadata,
    sa.Column("franchise_id", sa.ForeignKey("franchises.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("archive_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
)

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    sa.Column("role_id", sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("permission_id", sa.ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True),
)

user_roles = Table(
    "user_roles",
    Base.metadata,
    sa.Column("user_id", sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("role_id", sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)

archive_entry_relations = Table(
    "archive_entry_relations",
    Base.metadata,
    sa.Column("source_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("target_entry_id", sa.ForeignKey("archive_entries.id", ondelete="CASCADE"), primary_key=True),
    sa.Column("relationship_type", sa.Enum(RelationshipType, name="relationship_type"), nullable=False),
)
