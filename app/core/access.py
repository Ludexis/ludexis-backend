from contextlib import contextmanager
from contextvars import ContextVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.archive_entry import ArchiveEntry
from app.models.collection import Collection
from app.models.user import User
from app.models.user_entry_flag import UserEntryFlag
from app.utils.enums import PermissionName

# Sources whose records and art may hold restricted content; they are used only for users allowed it.
RESTRICTED_PROVIDERS = {"VNDB"}

# Background jobs run as the user who started them, so provider choice follows that user's access.
_acting_user_id: ContextVar[str | None] = ContextVar("acting_user_id", default=None)


@contextmanager
def acting_as(user_id: str | None):
    token = _acting_user_id.set(user_id)
    try:
        yield
    finally:
        _acting_user_id.reset(token)


def is_admin(user: User) -> bool:
    return user.is_superuser or any(
        permission.name == PermissionName.ACCESS_ADMIN.value for role in user.roles for permission in role.permissions
    )


def restricted_sources_allowed(db: Session) -> bool:
    allowed = db.query(User).filter(User.deleted_at.is_(None), User.is_active.is_(True), User.allow_restricted.is_(True))
    user_id = _acting_user_id.get()
    if user_id:
        return allowed.filter(User.id == user_id).count() > 0
    # Scheduled work has no user, so it follows the administrators.
    return any(is_admin(user) for user in allowed)


def entry_filters(user: User | None) -> list:
    """SQL filters leaving out the games this user may not see; no user means internal work that sees all."""
    if user is None:
        return []
    filters = []
    if not user.allow_restricted:
        filters.append(ArchiveEntry.restricted.is_(False))
    if user.blocked_collection_ids:
        filters.append(~ArchiveEntry.collections.any(Collection.id.in_(user.blocked_collection_ids)))
    return filters


def flagged_ids(user: User, flag: str):
    return sa.select(UserEntryFlag.archive_entry_id).where(UserEntryFlag.user_id == user.id, getattr(UserEntryFlag, flag).is_(True))


def annotate_flags(db: Session, user: User, entries: list[ArchiveEntry]) -> list[ArchiveEntry]:
    """Sets is_favorite and is_completed on each entry for this user."""
    ids = [entry.id for entry in entries]
    flags = {
        flag.archive_entry_id: flag
        for flag in db.query(UserEntryFlag).filter(UserEntryFlag.user_id == user.id, UserEntryFlag.archive_entry_id.in_(ids))
    } if ids else {}
    for entry in entries:
        flag = flags.get(entry.id)
        entry.is_favorite = bool(flag and flag.favorite)
        entry.is_completed = bool(flag and flag.completed)
    return entries


def set_flags(db: Session, user: User, entries: list[ArchiveEntry], favorite: bool | None, completed: bool | None) -> UserEntryFlag:
    """Marks every given entry (a game's versions share one card) and returns the first one's flag."""
    flags = []
    for entry in entries:
        flag = db.get(UserEntryFlag, (user.id, entry.id)) or UserEntryFlag(user_id=user.id, archive_entry_id=entry.id)
        if favorite is not None:
            flag.favorite = favorite
        if completed is not None:
            flag.completed = completed
        db.add(flag)
        flags.append(flag)
    db.commit()
    return flags[0]


def visible_names(relation, user: User | None):
    """Filter for developers, tags and the like: names whose live games are all hidden from this user drop out."""
    rules = entry_filters(user)
    if not rules:
        return sa.true()
    live = ArchiveEntry.deleted_at.is_(None)
    return sa.or_(~relation.any(live), relation.any(sa.and_(live, *rules)))
