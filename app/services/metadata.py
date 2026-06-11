from typing import Iterable
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
from app.models.job_history import JobHistory
from app.utils.enums import JobStatus

from app.repositories.genre import GenreRepository
from app.repositories.developer import DeveloperRepository
from app.repositories.publisher import PublisherRepository

from app.core.logging import get_logger

logger = get_logger(__name__)

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
        logger.info(
            "Metadata auto-match started",
            extra={
                "title": title,
            },
        )
        results = self.search(
            title,
            preferred_providers=["IGDB"],
            limit=20,
        )
        if not results:
            logger.info(
                "Metadata auto-match returned no results",
                extra={
                    "title": title,
                },
            )
            return None, 0.0
        best_result = None
        best_score = 0.0
        for result in results:
            score = SequenceMatcher(
                None,
                title.lower(),
                result.title.lower(),
            ).ratio()
            result.score = score
            if score > best_score:
                best_score = score
                best_result = result
        logger.info(
            "Metadata auto-match completed",
            extra={
                "title": title,
                "provider": best_result.provider,
                "provider_id": best_result.provider_id,
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
        if match is None:
            archive.metadata_status = (
                MetadataStatus.UNMATCHED
            )
            archive.last_metadata_refresh = (
                datetime.now(UTC)
            )
            db.add(archive)
            db.commit()
            logger.info(
                "Archive metadata unmatched",
                extra={
                    "archive_id": archive.id,
                    "title": archive.title,
                },
            )
            return False
        if score >= 0.85:
            archive.metadata_status = (
                MetadataStatus.MATCHED
            )
        elif score >= 0.70:
            archive.metadata_status = (
                MetadataStatus.PARTIAL
            )
        else:
            archive.metadata_status = (
                MetadataStatus.UNMATCHED
            )
        archive.metadata_source = (
            match.provider
        )
        archive.metadata_source_code = (
            match.provider_id
        )
        details = self.get_details(
            match.provider,
            match.provider_id,
        )
        if details:

            if details.description:
                archive.description = (
                    details.description
                )

            if details.release_date:
                archive.release_date = (
                    details.release_date
                )
        archive.last_metadata_refresh = (
            datetime.now(UTC)
        )
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
        return (archive.metadata_status!= MetadataStatus.UNMATCHED)

    def search(self, query: str, preferred_providers: list[str] | None = None, limit: int = 20) -> list[MetadataSearchResult]:
        logger.info(
            "Metadata search started",
            extra={
                "query": query,
                "preferred_providers": preferred_providers,
                "limit": limit,
            },
        )
        providers = self._get_providers(preferred_providers)
        results: list[MetadataSearchResult] = []

        for provider in providers:
            try:
                provider_results = provider.search(query, limit=limit)
                logger.info(
                    "Metadata provider search completed",
                    extra={
                        "provider": provider.name,
                        "query": query,
                        "result_count": len(provider_results),
                    },
                )
            except NotImplementedError:
                continue
            except Exception:
                logger.exception(
                    "Metadata provider search failed",
                    extra={
                        "provider": provider.name,
                        "query": query,
                    },
                )
                continue
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
            archive.title
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
    
    def refresh_all(self, db: Session, job_id: str | None = None,) -> dict:
        logger.info(
            "Metadata batch refresh started",
            extra={
                "job_id": job_id,
            },
        )
        archives = (
            db.query(ArchiveEntry)
            .filter(
                ArchiveEntry.metadata_status
                == MetadataStatus.MATCHED
            )
            .all()
        )
        refreshed = 0
        failed = 0
        for archive in archives:
            if job_id:
                job = (db.query(JobHistory).filter(JobHistory.id== job_id).first())
                if (job and job.status==JobStatus.CANCELED):
                    logger.warning(
                        "Metadata batch refresh cancelled",
                        extra={
                            "job_id": job_id,
                        },
                    )
                    return {
                        "refreshed": refreshed,
                        "failed": failed,
                        "cancelled": True,
                    }
            if archive.metadata_override:
                logger.info(
                    "Metadata refresh skipped",
                    extra={
                        "archive_id": archive.id,
                        "reason": "metadata_override",
                    },
                )
                continue
            if self.refresh_archive(
                db,
                archive,
            ):
                refreshed += 1
            else:
                failed += 1
        logger.info(
            "Metadata batch refresh completed",
            extra={
                "job_id": job_id,
                "refreshed": refreshed,
                "failed": failed,
            },
        )
        return {
            "refreshed": refreshed,
            "failed": failed,
        }
    
    def get_merged_details(
        self,
        title: str,
    ) -> MetadataDetails | None:

        match, score = self.auto_match(
            title
        )

        if match is None:
            return None

        igdb_details = self.get_details(
            match.provider,
            match.provider_id,
        )

        if igdb_details is None:
            return None

        steam_results = SteamProvider().search(
            title,
            limit=1,
        )

        steam_details = None

        if steam_results:
            steam_details = (
                SteamProvider().get_details(
                    steam_results[0].provider_id
                )
            )

        return self.conflict_resolver.resolve(
            igdb_details,
            steam_details,
        )