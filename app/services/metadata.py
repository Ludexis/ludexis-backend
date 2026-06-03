from typing import Iterable
from difflib import SequenceMatcher
from datetime import UTC, datetime
from sqlalchemy.orm import Session
from app.models.archive_entry import ArchiveEntry
from app.utils.enums import MetadataStatus
from app.providers import GOGProvider, IGDBProvider, ManualProvider, SteamProvider
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult

from app.models.genre import Genre
from app.models.developer import Developer
from app.models.publisher import Publisher

from app.repositories.genre import GenreRepository
from app.repositories.developer import DeveloperRepository
from app.repositories.publisher import PublisherRepository

class MetadataService:
    def __init__(self, providers: list[MetadataProvider] | None = None) -> None:
        self.providers = providers or [
            IGDBProvider(),
            SteamProvider(),
            GOGProvider(),
            ManualProvider(),
        ]
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
        results = self.search(
            title,
            preferred_providers=["IGDB"],
            limit=20,
        )
        if not results:
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
        return best_result, best_score
    
    def auto_match_archive(self, db: Session, archive: ArchiveEntry, ) -> bool:
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
        return (archive.metadata_status!= MetadataStatus.UNMATCHED)

    def search(self, query: str, preferred_providers: list[str] | None = None, limit: int = 20) -> list[MetadataSearchResult]:
        providers = self._get_providers(preferred_providers)
        results: list[MetadataSearchResult] = []

        for provider in providers:
            try:
                provider_results = provider.search(query, limit=limit)
            except NotImplementedError:
                continue
            if provider_results:
                results.extend(provider_results)
                break

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
        if (
            not archive.metadata_source
            or
            not archive.metadata_source_code
        ):
            return False

        details = self.get_details(
            archive.metadata_source,
            archive.metadata_source_code,
        )
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
        if not details:
            return False
        if details.description:
            archive.description = details.description
        if details.release_date:
            archive.release_date = details.release_date
        archive.last_metadata_refresh = (
            datetime.now(UTC)
        )
        db.add(archive)
        db.commit()
        return True
    
    def refresh_all(self, db: Session,) -> dict:
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
            if self.refresh_archive(
                db,
                archive,
            ):
                refreshed += 1
            else:
                failed += 1
        return {
            "refreshed": refreshed,
            "failed": failed,
        }