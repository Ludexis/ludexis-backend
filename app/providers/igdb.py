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
            involved_companies.developer,
            involved_companies.publisher,
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

        cover_urls = []
        banner_urls = []
        logo_urls = []
        artwork_urls = []

        cover = game.get("cover")

        if cover and cover.get("url"):
            url = (
                "https:" + cover["url"]
            )
            url = url.replace(
                "t_thumb",
                "t_cover_big",
            )
            cover_urls.append(
                url
            )

        for artwork in game.get(
            "artworks",
            [],
        ):
            if artwork.get("url"):
                url = (
                    "https:" + artwork["url"]
                )
                url = url.replace(
                    "t_thumb",
                    "t_1080p",
                )
                artwork_urls.append(
                    url
                )

        developers = []
        publishers = []

        for company in game.get("involved_companies", [],):
            company_obj = company.get("company", {},)
            company_name = company_obj.get("name")
            if not company_name:
                continue
            if company.get("developer"):
                developers.append(
                    company_name
                )
            if company.get("publisher"):
                publishers.append(
                    company_name
                )

        return MetadataDetails(
            provider=self.name,
            provider_id=str(game["id"]),
            title=game["name"],
            description=game.get("summary"),
            release_date=release_date,
            genres=genres,
            developers=developers,
            publishers=publishers,
            tags=[],
            cover_urls=cover_urls,
            banner_urls=banner_urls,
            logo_urls=logo_urls,
            artwork_urls=artwork_urls,
        )

    def download_artwork(
        self,
        external_id: str,
    ) -> bytes | None:
        return None