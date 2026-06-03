from datetime import datetime
import requests
from html import unescape
from datetime import datetime

from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import (
    MetadataDetails,
    MetadataSearchResult,
)

class SteamProvider(MetadataProvider):
    name = "Steam"
    priority = 20
    SEARCH_URL = ("https://store.steampowered.com/api/storesearch")
    APP_URL = ("https://store.steampowered.com/api/appdetails")

    def search(self, query: str, limit: int = 20,) -> list[MetadataSearchResult]:
        response = requests.get(
            self.SEARCH_URL,
            params={
                "term": query,
                "l": "english",
                "cc": "US",
            },
            timeout=20,
        )
        response.raise_for_status()
        data = response.json()
        results = []
        for item in data.get("items", [])[:limit]:
            results.append(
                MetadataSearchResult(
                    provider=self.name,
                    provider_id=str(
                        item["id"]
                    ),
                    title=item["name"],
                    summary=None,
                    release_date=None,
                )
            )
        return results

    def get_details(self, external_id: str,) -> MetadataDetails | None:
        response = requests.get(
            self.APP_URL,
            params={
                "appids": external_id,
            },
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        app = payload.get(
            str(external_id)
        )
        if not app:
            return None
        data = app.get("data")
        if not data:
            return None
        genres = [
            genre["description"]
            for genre in data.get(
                "genres",
                []
            )
        ]
        developers = (
            data.get(
                "developers",
                []
            )
        )
        publishers = (
            data.get(
                "publishers",
                []
            )
        )
        artwork = []

        for key in (
            "header_image",
            "capsule_image",
            "capsule_imagev5",
        ):

            url = data.get(key)

            if url:
                artwork.append(url)

        release_date = None
        try:
            release_string = (data.get("release_date",{}).get("date"))
            if release_string:
                for fmt in (
                    "%d %b, %Y",
                    "%b %d, %Y",
                ):
                    try:
                        release_date = (datetime.strptime(release_string,fmt,).date())
                        break
                    except ValueError:
                        pass
        except Exception:
            pass

        return MetadataDetails(
            provider=self.name,
            provider_id=str(
                external_id
            ),
            title=data["name"],
            description=unescape(
                data.get(
                    "short_description",
                    "",
                )
            ),
            genres=genres,
            developers=developers,
            publishers=publishers,
            tags=[],
            artwork_urls=artwork,
            release_date=release_date,
        )

    def download_artwork(self, external_id: str,) -> bytes | None:
        return None