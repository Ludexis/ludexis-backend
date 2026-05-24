from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult


class GOGProvider(MetadataProvider):
    name = "GOG"
    priority = 30

    def search(self, query: str, limit: int = 20) -> list[MetadataSearchResult]:
        return []

    def get_details(self, external_id: str) -> MetadataDetails | None:
        return None

    def download_artwork(self, external_id: str) -> bytes | None:
        return None
