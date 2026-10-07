import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.archive_entry import ArchiveEntry
from app.models.association_tables import archive_entry_relations
from app.models.collection import Collection
from app.utils.enums import MetadataStatus, RelationshipType
from app.utils.normalization import parse_archive_name, title_key

logger = get_logger(__name__)

OLDEST = datetime.min.replace(tzinfo=timezone.utc)


def version_order(version: str | None) -> tuple:
    # "1.10" > "1.9" and "1.0e" > "1.0"; entries without a version sort first.
    return tuple((int(part), "") if part.isdigit() else (0, part) for part in re.findall(r"\d+|[a-z]+", (version or "").lower()))


class GroupingService:
    """Keeps versions of one game under a primary entry and gathers numbered episodes into a collection."""

    def regroup(self, db: Session) -> dict[str, int]:
        # regroups the whole library on every scan; fine for tens of thousands of entries,
        # restrict to the touched groups if scans get slow.
        entries = db.query(ArchiveEntry).filter(ArchiveEntry.deleted_at.is_(None)).all()
        groups: dict[str, list[ArchiveEntry]] = defaultdict(list)
        series: dict[str, list[ArchiveEntry]] = defaultdict(list)
        series_titles: dict[str, str] = {}

        # Keys come from the file name, not the title, so a user's title edit never splits a group.
        for entry in entries:
            parsed = parse_archive_name(Path(entry.file_path).name)
            entry.group_key = title_key(parsed.title) or None
            entry.episode = parsed.episode if parsed.episode is not None else parsed.part
            entry.season = parsed.season
            entry.series_key = title_key(parsed.series_title) if parsed.series_title else None
            if entry.group_key:
                groups[entry.group_key].append(entry)
            else:
                entry.is_primary_version = True
            if entry.series_key:
                series[entry.series_key].append(entry)
                series_titles.setdefault(entry.series_key, parsed.series_title)

        self._merge_matched(groups)

        for members in groups.values():
            primary = max(members, key=lambda e: (version_order(e.version), e.modified_time or OLDEST, e.created_at or OLDEST))
            for entry in members:
                entry.is_primary_version = entry is primary

        collections = 0
        for key, members in series.items():
            # Versions of a single episode are not a series.
            if len({entry.group_key for entry in members}) < 2:
                continue
            collection = db.query(Collection).filter(Collection.auto_key == key).first()
            if collection is None:
                collection = Collection(name=series_titles[key], auto_key=key, visibility="public")
                db.add(collection)
            elif collection.deleted_at is not None:
                # The user removed this series collection; do not bring it back.
                continue
            for entry in members:
                if entry not in collection.archive_entries:
                    collection.archive_entries.append(entry)
            self._link_episodes(db, members)
            collections += 1

        db.commit()
        stats = {
            "version_groups": sum(1 for members in groups.values() if len(members) > 1),
            "series_collections": collections,
        }
        logger.info("Regrouped library", extra=stats)
        return stats

    def _merge_matched(self, groups: dict[str, list[ArchiveEntry]]) -> None:
        # File names of one game can differ beyond the version ("Game-v1_Ext" vs "Game-v2"); groups whose
        # entries are matched to the same provider record are one game. Episode and season stay part of the
        # identity so episodes sharing one provider record remain separate cards.
        keys_by_identity: dict[tuple, set[str]] = defaultdict(set)
        for key, members in groups.items():
            for entry in members:
                if entry.metadata_source_code and entry.metadata_status in (MetadataStatus.MATCHED, MetadataStatus.MANUAL):
                    identity = (entry.metadata_source, entry.metadata_source_code, entry.season, entry.episode)
                    keys_by_identity[identity].add(key)

        parent: dict[str, str] = {}

        def root(key: str) -> str:
            while parent.get(key, key) != key:
                key = parent[key]
            return key

        for keys in keys_by_identity.values():
            roots = {root(key) for key in keys}
            target = min(roots)
            for key in roots:
                parent[key] = target

        for key in list(groups):
            target = root(key)
            if target != key:
                for entry in groups.pop(key):
                    entry.group_key = target
                    groups[target].append(entry)

    def _link_episodes(self, db: Session, members: list[ArchiveEntry]) -> None:
        # Each episode's primary version points at the next one (EPISODE), rebuilt so a new primary version takes over.
        relations = archive_entry_relations.c
        db.execute(
            archive_entry_relations.delete().where(
                relations.relationship_type == RelationshipType.EPISODE,
                relations.source_entry_id.in_([entry.id for entry in members]),
            )
        )
        episodes = sorted(
            (entry for entry in members if entry.is_primary_version),
            key=lambda entry: (entry.season or 0, entry.episode or 0),
        )
        rows = [
            {"source_entry_id": current.id, "target_entry_id": following.id, "relationship_type": RelationshipType.EPISODE}
            for current, following in zip(episodes, episodes[1:])
        ]
        if rows:
            db.execute(insert(archive_entry_relations).values(rows).on_conflict_do_nothing())

    def siblings(self, db: Session, entry: ArchiveEntry) -> list[ArchiveEntry]:
        if not entry.group_key:
            return []
        return (
            db.query(ArchiveEntry)
            .filter(
                ArchiveEntry.group_key == entry.group_key,
                ArchiveEntry.id != entry.id,
                ArchiveEntry.deleted_at.is_(None),
            )
            .all()
        )
