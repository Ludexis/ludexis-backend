from datetime import UTC, datetime

from app.providers.igdb_client import IGDBClient
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult


class IGDBProvider(MetadataProvider):
    name = "IGDB"
    priority = 10

    def __init__(self) -> None:
        self.client = IGDBClient()

    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[MetadataSearchResult]:

        if not query:
            return []

        igdb_query = f"""
        search "{query}";
        fields
            name,
            summary,
            first_release_date;
        limit {limit};
        """

        results = self.client.post(
            "games",
            igdb_query,
        )

        metadata_results: list[MetadataSearchResult] = []

        for game in results:

            release_date = None

            if game.get("first_release_date"):
                release_date = datetime.fromtimestamp(
                    game["first_release_date"],
                    tz=UTC,
                ).date()

            metadata_results.append(
                MetadataSearchResult(
                    provider=self.name,
                    provider_id=str(game["id"]),
                    title=game["name"],
                    summary=game.get("summary"),
                    release_date=release_date,
                    score=None,
                )
            )

        return metadata_results

    def get_details(
        self,
        external_id: str,
    ) -> MetadataDetails | None:

        igdb_query = f"""
        fields
            name,
            summary,
            first_release_date,
            genres.name,
            involved_companies.company.name,
            cover.url,
            artworks.url;
        where id = {external_id};
        """

        results = self.client.post(
            "games",
            igdb_query,
        )

        if not results:
            return None

        game = results[0]

        release_date = None

        if game.get("first_release_date"):
            release_date = datetime.fromtimestamp(
                game["first_release_date"],
                tz=UTC,
            ).date()

        genres = [
            genre["name"]
            for genre in game.get("genres", [])
            if genre.get("name")
        ]

        artwork_urls = []

        cover = game.get("cover")

        if cover and cover.get("url"):
            artwork_urls.append(
                "https:" + cover["url"]
            )

        for artwork in game.get(
            "artworks",
            [],
        ):
            if artwork.get("url"):
                artwork_urls.append(
                    "https:" + artwork["url"]
                )

        company_names = []

        for company in game.get(
            "involved_companies",
            [],
        ):
            company_obj = company.get(
                "company",
                {},
            )

            if company_obj.get("name"):
                company_names.append(
                    company_obj["name"]
                )

        return MetadataDetails(
            provider=self.name,
            provider_id=str(game["id"]),
            title=game["name"],
            description=game.get("summary"),
            release_date=release_date,
            genres=genres,
            developers=company_names,
            publishers=company_names,
            tags=[],
            artwork_urls=artwork_urls,
        )

    def download_artwork(
        self,
        external_id: str,
    ) -> bytes | None:
        return None