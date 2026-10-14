import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import PureWindowsPath

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


def version_rank(entry: ArchiveEntry) -> tuple:
    # Versions of a game that spans episodes rank by episode first, so the latest episode leads the card.
    return (entry.season or 0, entry.episode or 0, version_order(entry.version), entry.modified_time or OLDEST, entry.created_at or OLDEST)


def _identity(entry: ArchiveEntry) -> tuple[str, str] | None:
    if entry.metadata_source_code and entry.metadata_status in (MetadataStatus.MATCHED, MetadataStatus.MANUAL):
        return entry.metadata_source, entry.metadata_source_code
    return None


def _game_keys(entry: ArchiveEntry) -> set[tuple]:
    # A matched entry is known by its provider record and by the name it was identified as, so one game
    # matched on two providers (or one record per episode) still counts as one.
    identity = _identity(entry)
    if identity is None:
        return set()
    keys = {("record", *identity)}
    if title_key(entry.title):
        keys.add(("title", title_key(entry.title)))
    return keys


def _components(items: list, keys) -> list[list]:
    """The items linked to each other through any shared key, as separate groups in first-seen order."""
    parent = list(range(len(items)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    owner: dict = {}
    for index, item in enumerate(items):
        for key in keys(item):
            if key in owner:
                parent[find(index)] = find(owner[key])
            else:
                owner[key] = index
    components: dict[int, list] = defaultdict(list)
    for index, item in enumerate(items):
        components[find(index)].append(item)
    return list(components.values())


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
        # PureWindowsPath splits on both separators, so a catalogue scanned on Windows groups the same on Linux.
        for entry in entries:
            parsed = parse_archive_name(PureWindowsPath(entry.file_path).name)
            identity = _identity(entry)
            entry.group_key = title_key(parsed.title) or (f"#{identity[0]}:{identity[1]}" if identity else None)
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
            primary = max(members, key=version_rank)
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
        # Entries matched to one provider record, or identified as the same name, are one game whatever their
        # file names or episodes ("Game-v1_Ext" and "Game-Ep2-v3" alike). A file-name group whose entries were
        # matched to different games is split by game, so identifying one file as another game moves only that
        # file; its unmatched entries stay together.
        buckets: dict[str, list[ArchiveEntry]] = {}
        keys_of: dict[str, set[tuple]] = {}
        for key, members in groups.items():
            games = _components([entry for entry in members if _game_keys(entry)], _game_keys)
            if len(games) <= 1:
                buckets[key] = members
                keys_of[key] = set().union(*map(_game_keys, members))
                continue
            unmatched = [entry for entry in members if not _game_keys(entry)]
            if unmatched:
                buckets[key] = unmatched
            for game in games:
                source, code = min(_identity(entry) for entry in game)
                label = f"{key}#{source}:{code}"[:256]
                buckets[label] = game
                keys_of[label] = set().union(*map(_game_keys, game))

        groups.clear()
        for labels in _components(list(buckets), lambda label: keys_of.get(label, ())):
            target = min(labels)
            for label in labels:
                for entry in buckets[label]:
                    entry.group_key = target
                groups[target].extend(buckets[label])

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
