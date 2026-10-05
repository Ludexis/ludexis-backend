import re
import threading
import time
from datetime import date

import requests

from app.core.logging import get_logger
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult

logger = get_logger(__name__)

# VNDB allows 200 requests per 5 minutes; one request every 1.5 s stays under it.
MIN_INTERVAL_SECONDS = 1.5
# Some networks block VNDB outright; after a connection failure skip it for a while instead of
# waiting on a timeout for every entry.
BACKOFF_SECONDS = 600
TAG_LIMIT = 15
MIN_TAG_RATING = 2.0
DETAIL_FIELDS = (
    "title, description, released, developers.name, tags.name, tags.rating, tags.spoiler, "
    "image.url, screenshots.url"
)


def _parse_released(value: str | None) -> date | None:
    # VNDB dates may be partial ("2019-04") or "TBA".
    if not value or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return None
    return date.fromisoformat(value)


def _strip_markup(text: str | None) -> str | None:
    if not text:
        return text
    text = re.sub(r"\[url=[^\]]*\](.*?)\[/url\]", r"\1", text, flags=re.DOTALL)
    return re.sub(r"\[/?(?:b|i|u|s|spoiler|quote|raw|code)\]", "", text).strip()


class VNDBProvider(MetadataProvider):
    name = "VNDB"
    priority = 5
    API_URL = "https://api.vndb.org/kana/vn"

    _lock = threading.Lock()
    _last_request = 0.0
    _down_until = 0.0

    def _query(self, payload: dict) -> list[dict]:
        cls = type(self)
        if time.monotonic() < cls._down_until:
            return []
        with cls._lock:
            wait = cls._last_request + MIN_INTERVAL_SECONDS - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            cls._last_request = time.monotonic()
        try:
            response = requests.post(self.API_URL, json=payload, timeout=(5, 20))
        except requests.ConnectionError:
            cls._down_until = time.monotonic() + BACKOFF_SECONDS
            logger.warning("VNDB unreachable, skipping it for a while", extra={"backoff_seconds": BACKOFF_SECONDS})
            return []
        response.raise_for_status()
        return response.json().get("results", [])

    def search(self, query: str, limit: int = 20) -> list[MetadataSearchResult]:
        results = self._query({
            "filters": ["search", "=", query],
            "fields": "title, alttitle, released, image.thumbnail",
            "results": min(limit, 100),
        })
        return [
            MetadataSearchResult(
                provider=self.name,
                provider_id=item["id"],
                title=item["title"],
                release_date=_parse_released(item.get("released")),
                cover_url=(item.get("image") or {}).get("thumbnail"),
            )
            for item in results
        ]

    def get_details(self, external_id: str) -> MetadataDetails | None:
        results = self._query({"filters": ["id", "=", external_id], "fields": DETAIL_FIELDS})
        if not results:
            return None
        vn = results[0]
        tags = sorted(
            (tag for tag in vn.get("tags", []) if tag.get("spoiler", 0) == 0 and tag.get("rating", 0) >= MIN_TAG_RATING),
            key=lambda tag: tag["rating"],
            reverse=True,
        )
        image = vn.get("image") or {}
        return MetadataDetails(
            provider=self.name,
            provider_id=vn["id"],
            title=vn["title"],
            description=_strip_markup(vn.get("description")),
            release_date=_parse_released(vn.get("released")),
            developers=[developer["name"] for developer in vn.get("developers", []) if developer.get("name")],
            tags=[tag["name"] for tag in tags[:TAG_LIMIT]],
            cover_urls=[image["url"]] if image.get("url") else [],
            artwork_urls=[shot["url"] for shot in vn.get("screenshots", []) if shot.get("url")],
        )

    def download_artwork(self, external_id: str) -> bytes | None:
        return None
