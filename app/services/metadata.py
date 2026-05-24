from typing import Iterable

from app.providers import GOGProvider, IGDBProvider, ManualProvider, SteamProvider
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult


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
