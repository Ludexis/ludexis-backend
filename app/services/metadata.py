import re
from difflib import SequenceMatcher
from datetime import UTC, datetime
from sqlalchemy.orm import Session
from app.models.archive_entry import ArchiveEntry
from app.utils.enums import MetadataStatus
from app.providers import GOGProvider, IGDBProvider, ManualProvider, SteamProvider
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult
from app.services.metadata_conflict import MetadataConflictResolver

from app.models.genre import Genre
from app.models.developer import Developer
from app.models.publisher import Publisher

from app.repositories.genre import GenreRepository
from app.repositories.developer import DeveloperRepository
from app.repositories.publisher import PublisherRepository

from app.core.logging import get_logger
from app.core.metrics import metadata_searches_total

logger = get_logger(__name__)

MATCHED_THRESHOLD = 0.85
PARTIAL_THRESHOLD = 0.70


def title_similarity(left: str, right: str) -> float:
    left_words = re.findall(r"[a-z0-9]+", left.lower())
    right_words = re.findall(r"[a-z0-9]+", right.lower())
    left_joined, right_joined = "".join(left_words), "".join(right_words)
    # Archive names often lose spaces and punctuation, so identical letters and digits are a full match.
    if left_joined == right_joined:
        return 1.0 if left_joined else 0.0
    # Otherwise average character similarity with shared whole words, so a short title like
    # "Red Moon" does not match "Bred Moon" on characters alone.
    characters = SequenceMatcher(None, left_joined, right_joined).ratio()
    shared = set(left_words) & set(right_words)
    words = len(shared) / len(set(left_words) | set(right_words))
    return (characters + words) / 2

class MetadataService:
    def __init__(self, providers: list[MetadataProvider] | None = None) -> None:
        self.providers = providers or [
            IGDBProvider(),
            SteamProvider(),
            GOGProvider(),
            ManualProvider(),
        ]
        self.conflict_resolver = (MetadataConflictResolver())
        self.providers.sort(key=lambda provider: provider.priority)
        self.provider_map = {provider.name: provider for provider in self.providers}
        self.genre_repo = GenreRepository()
        self.developer_repo = DeveloperRepository()
        self.publisher_repo = PublisherRepository()

    def _sync_genres(self, db, archive, genres: list[str],):
        archive.genres.clear()
        for name in genres:
            genre = self.genre_repo.get_by_name(
                db,
                name,
            )
            if genre is None:
                genre = Genre(
                    name=name,
                )
                db.add(genre)
                db.flush()
            archive.genres.append(
                genre
            )

    def _sync_developers(self, db, archive, developers: list[str],):
        archive.developers.clear()
        for name in developers:
            developer = (
                self.developer_repo.get_by_name(
                    db,
                    name,
                )
            )
            if developer is None:
                developer = Developer(
                    name=name,
                )
                db.add(developer)
                db.flush()
            archive.developers.append(
                developer
            )

    def _sync_publishers(self, db, archive, publishers: list[str],):
        archive.publishers.clear()
        for name in publishers:
            publisher = (
                self.publisher_repo.get_by_name(
                    db,
                    name,
                )
            )
            if publisher is None:
                publisher = Publisher(
                    name=name,
                )
                db.add(publisher)
                db.flush()
            archive.publishers.append(
                publisher
            )

    def auto_match(self, title: str, ) -> tuple[MetadataSearchResult | None, float]:
        # Providers are tried in priority order (IGDB first); a confident match stops the search,
        # otherwise the best candidate across all providers wins.
        best_result = None
        best_score = 0.0
        for provider in self._get_providers(["IGDB"]):
            for result in self._search_provider(provider, title, limit=20):
                score = title_similarity(title, result.title)
                result.score = score
                if score > best_score:
                    best_score = score
                    best_result = result
            if best_score >= MATCHED_THRESHOLD:
                break
        logger.info(
            "Metadata auto-match completed",
            extra={
                "title": title,
                "provider": best_result.provider if best_result else None,
                "provider_id": best_result.provider_id if best_result else None,
                "score": round(best_score, 3),
            },
        )
        return best_result, best_score

    def auto_match_archive(self, db: Session, archive: ArchiveEntry, ) -> bool:
        logger.info(
            "Archive metadata matching started",
            extra={
                "archive_id": archive.id,
                "title": archive.title,
            },
        )
        if archive.metadata_override:
            logger.info(
                "Archive metadata matching skipped",
                extra={
                    "archive_id": archive.id,
                    "reason": "metadata_override",
                },
            )
            return False
        match, score = self.auto_match(
            archive.title,
        )
        archive.last_metadata_refresh = datetime.now(UTC)
        archive.metadata_confidence = round(score, 3)
        if match is None or score < PARTIAL_THRESHOLD:
            # A weak candidate is not recorded as the source, so refreshes never enrich from the wrong game.
            archive.metadata_status = MetadataStatus.UNMATCHED
            db.add(archive)
            db.commit()
            logger.info(
                "Archive metadata unmatched",
                extra={
                    "archive_id": archive.id,
                    "title": archive.title,
                    "score": round(score, 3),
                },
            )
            return False
        archive.metadata_status = (
            MetadataStatus.MATCHED
            if score >= MATCHED_THRESHOLD
            else MetadataStatus.PARTIAL
        )
        archive.metadata_source = match.provider
        archive.metadata_source_code = match.provider_id
        db.add(archive)
        db.commit()
        logger.info(
            "Archive metadata matched",
            extra={
                "archive_id": archive.id,
                "provider": match.provider,
                "provider_id": match.provider_id,
                "status": archive.metadata_status.value,
            },
        )
        self.refresh_archive(db, archive)
        return (archive.metadata_status!= MetadataStatus.UNMATCHED)

    def search(self, query: str, preferred_providers: list[str] | None = None, limit: int = 20) -> list[MetadataSearchResult]:
        metadata_searches_total.inc()
        logger.info(
            "Metadata search started",
            extra={
                "query": query,
                "preferred_providers": preferred_providers,
                "limit": limit,
            },
        )
        results: list[MetadataSearchResult] = []
        for provider in self._get_providers(preferred_providers):
            provider_results = self._search_provider(provider, query, limit)
            if provider_results:
                results.extend(provider_results)
                break
        logger.info(
            "Metadata search completed",
            extra={
                "query": query,
                "total_results": len(results),
            },
        )
        return results

    def _search_provider(self, provider: MetadataProvider, query: str, limit: int) -> list[MetadataSearchResult]:
        try:
            provider_results = provider.search(query, limit=limit)
        except NotImplementedError:
            return []
        except Exception:
            logger.exception(
                "Metadata provider search failed",
                extra={
                    "provider": provider.name,
                    "query": query,
                },
            )
            return []
        logger.info(
            "Metadata provider search completed",
            extra={
                "provider": provider.name,
                "query": query,
                "result_count": len(provider_results),
            },
        )
        return provider_results

    def get_details(self, provider_name: str | None, provider_id: str) -> MetadataDetails | None:
        if provider_name:
            provider = self._get_provider(provider_name)
            if provider:
                return provider.get_details(provider_id)
            return None

        for provider in self.providers:
            details = provider.get_details(provider_id)
            if details:
                return details
        return None

    def download_artwork(self, provider_name: str, provider_id: str) -> bytes | None:
        provider = self._get_provider(provider_name)
        if provider is None:
            return None
        return provider.download_artwork(provider_id)

    def _get_provider(self, name: str) -> MetadataProvider | None:
        return self.provider_map.get(name)

    def _get_providers(self, preferred_providers: list[str] | None) -> list[MetadataProvider]:
        if not preferred_providers:
            return self.providers

        prioritized = [self.provider_map[name] for name in preferred_providers if name in self.provider_map]
        return prioritized + [provider for provider in self.providers if provider.name not in {p.name for p in prioritized}]

    def refresh_archive(self, db: Session, archive: ArchiveEntry,) -> bool:
        logger.info(
            "Metadata refresh started",
            extra={
                "archive_id": archive.id,
                "title": archive.title,
            },
        )
        if archive.metadata_override:
            logger.info(
                "Metadata refresh skipped",
                extra={
                    "archive_id": archive.id,
                    "reason": "metadata_override",
                },
            )
            return False
        if (
            not archive.metadata_source
            or
            not archive.metadata_source_code
        ):
            return False

        details = self.get_merged_details(
            archive.title,
            archive.metadata_source,
            archive.metadata_source_code,
        )
        if not details:
            return False
        self._sync_genres(
            db,
            archive,
            details.genres,
        )

        self._sync_developers(
            db,
            archive,
            details.developers,
        )

        self._sync_publishers(
            db,
            archive,
            details.publishers,
        )
        if details.description:
            archive.description = details.description
        if details.release_date:
            archive.release_date = details.release_date
        archive.last_metadata_refresh = (
            datetime.now(UTC)
        )
        db.add(archive)
        db.commit()
        logger.info(
            "Metadata refresh completed",
            extra={
                "archive_id": archive.id,
                "provider": archive.metadata_source,
            },
        )
        return True
    
    def enrich_archive(self, db: Session, archive: ArchiveEntry,) -> bool:
        # Entries without a provider match are matched first; matched entries are refreshed from their stored source.
        if archive.metadata_override:
            return False
        if archive.metadata_source and archive.metadata_source_code:
            return self.refresh_archive(db, archive)
        return self.auto_match_archive(db, archive)

    def enrichment_candidates(self, db: Session, entry_ids: list[str] | None = None,) -> list[ArchiveEntry]:
        query = db.query(ArchiveEntry).filter(
            ArchiveEntry.deleted_at.is_(None),
            ArchiveEntry.metadata_override.is_(False),
        )
        if entry_ids is not None:
            return query.filter(ArchiveEntry.id.in_(entry_ids)).all()
        # Matched entries are refreshed; entries never attempted are matched. Entries that failed to match
        # are left for manual review instead of being searched again every night.
        return query.filter(
            (ArchiveEntry.metadata_source_code.is_not(None))
            | (ArchiveEntry.last_metadata_refresh.is_(None))
        ).all()

    def get_merged_details(
        self,
        title: str,
        provider_name: str | None = None,
        provider_id: str | None = None,
    ) -> MetadataDetails | None:
        if provider_id is None:
            match, score = self.auto_match(title)
            if match is None or score < PARTIAL_THRESHOLD:
                return None
            provider_name, provider_id = match.provider, match.provider_id

        primary = self.get_details(provider_name, provider_id)
        if primary is None:
            return None

        steam = self._get_provider("Steam")
        steam_details = None
        if steam is not None and provider_name != steam.name:
            steam_results = steam.search(title, limit=1)
            # Only merge a Steam record that is clearly the same game.
            if steam_results and title_similarity(title, steam_results[0].title) >= MATCHED_THRESHOLD:
                steam_details = steam.get_details(steam_results[0].provider_id)

        return self.conflict_resolver.resolve(primary, steam_details)
