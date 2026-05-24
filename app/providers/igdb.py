from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult


class IGDBProvider(MetadataProvider):
    name = "IGDB"
    priority = 10

    def search(self, query: str, limit: int = 20) -> list[MetadataSearchResult]:
        # Placeholder implementation for IGDB search.
        # Real integration will require credentials and the IGDB API.
        return [
            MetadataSearchResult(
                provider=self.name,
                provider_id="igdb_sample_1",
                title=f"{query} (IGDB sample)",
                summary="Stub result from IGDB provider.",
            )
        ] if query else []

    def get_details(self, external_id: str) -> MetadataDetails | None:
        # Stubbed details response. Replace with real IGDB mapping.
        return MetadataDetails(
            provider=self.name,
            provider_id=external_id,
            title="IGDB Sample Game",
            description="Metadata details returned from IGDB provider stub.",
            release_date=None,
            genres=["Action"],
            developers=["IGDB Studio"],
            publishers=["IGDB Publisher"],
            tags=["Sample", "Demo"],
            artwork_urls=["https://example.com/artwork.png"],
        )

    def download_artwork(self, external_id: str) -> bytes | None:
        # Artwork download is not implemented in this stub.
        return None
