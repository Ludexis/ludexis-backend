from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from app.schemas.metadata import MetadataDetails, MetadataSearchResult


class MetadataProvider(ABC):
    """Abstract metadata provider interface."""

    name: str
    priority: int = 100
    # Records and art from this source may hold restricted content; only users allowed it see it used.
    restricted: bool = False

    @abstractmethod
    def search(self, query: str, limit: int = 20, developer: str | None = None) -> list[MetadataSearchResult]:
        """developer, when the provider can filter by it, narrows the search to that studio's games."""
        raise NotImplementedError

    @abstractmethod
    def get_details(self, external_id: str) -> MetadataDetails | None:
        raise NotImplementedError
