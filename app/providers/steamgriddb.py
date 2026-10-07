from datetime import datetime, timezone
from urllib.parse import quote

import requests

API_URL = "https://www.steamgriddb.com/api/v2"
# Every candidate is downloaded to be scored, so only the community's top picks are offered.
PER_TYPE = 3
# Static images only; joke art is left out. NSFW art is allowed because a game's own cover may be flagged.
FILTERS = {"types": "static", "nsfw": "any", "humor": "false"}


class SteamGridDBClient:
    """Community artwork: portrait covers (grids), wide heroes and logos, for any game the site knows."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def _get(self, path: str, **params) -> list[dict]:
        response = requests.get(
            f"{API_URL}{path}",
            headers={"Authorization": f"Bearer {self.api_key}"},
            params=params,
            timeout=(5, 20),
        )
        if response.status_code == 404:
            return []
        response.raise_for_status()
        return response.json().get("data") or []

    def search(self, title: str) -> list[dict]:
        """Games named like the title: {id, name, year}; year is None when the site has no release date."""
        return [
            {
                "id": game["id"],
                "name": game["name"],
                "year": datetime.fromtimestamp(game["release_date"], timezone.utc).year if game.get("release_date") else None,
            }
            for game in self._get(f"/search/autocomplete/{quote(title, safe='')}")
        ]

    def artwork(self, game_id: int) -> dict[str, list[str]]:
        def urls(kind: str, **params) -> list[str]:
            return [image["url"] for image in self._get(f"/{kind}/game/{game_id}", **FILTERS, **params)[:PER_TYPE]]

        return {
            "cover_urls": urls("grids", dimensions="600x900,660x930,342x482"),
            "banner_urls": urls("heroes"),
            "logo_urls": urls("logos"),
        }
