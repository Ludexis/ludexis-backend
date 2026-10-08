from datetime import UTC, datetime

from app.providers.igdb_client import IGDBClient
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult


IGDB_KEYWORD_LIMIT = 10

class IGDBProvider(MetadataProvider):
    name = "IGDB"
    priority = 10

    def __init__(self) -> None:
        self.client = IGDBClient()

    def search(
        self,
        query: str,
        limit: int = 20,
        developer: str | None = None,
    ) -> list[MetadataSearchResult]:

        # Without Twitch credentials IGDB is skipped rather than failing every search.
        if not query or not self.client.configured():
            return []

        quote = lambda text: text.replace("\\", "").replace('"', '\\"')
        developer_filter = (
            f'where involved_companies.company.name ~ *"{quote(developer)}"*;'
            if developer
            else ""
        )
        igdb_query = f"""
        search "{quote(query)}";
        fields
            name,
            summary,
            first_release_date,
            cover.url,
            involved_companies.company.name,
            involved_companies.developer;
        {developer_filter}
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
                    cover_url=("https:" + game["cover"]["url"].replace("t_thumb", "t_cover_small")) if game.get("cover", {}).get("url") else None,
                    developers=[
                        company["company"]["name"]
                        for company in game.get("involved_companies", [])
                        if company.get("developer") and company.get("company", {}).get("name")
                    ],
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
            artworks.url,
            screenshots.url,
            franchises.name,
            collections.name,
            themes.name,
            keywords.name;
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

        for artwork in game.get("artworks", []) + game.get("screenshots", []):
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
            # Themes describe the game; keywords are numerous and noisy, so only the first few are kept.
            tags=list(dict.fromkeys(
                [item["name"] for item in game.get("themes", []) if item.get("name")]
                + [item["name"] for item in game.get("keywords", [])[:IGDB_KEYWORD_LIMIT] if item.get("name") and not item["name"].startswith("#")]
            )),
            franchises=list(dict.fromkeys(
                item["name"] for item in game.get("franchises", []) + game.get("collections", []) if item.get("name")
            )),
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