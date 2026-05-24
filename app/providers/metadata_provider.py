from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable

from app.schemas.metadata import MetadataDetails, MetadataSearchResult


class MetadataProvider(ABC):
    """Abstract metadata provider interface."""

    name: str
    priority: int = 100

    @abstractmethod
    def search(self, query: str, limit: int = 20) -> list[MetadataSearchResult]:
        raise NotImplementedError

    @abstractmethod
    def get_details(self, external_id: str) -> MetadataDetails | None:
        raise NotImplementedError

    @abstractmethod
    def download_artwork(self, external_id: str) -> bytes | None:
        raise NotImplementedError
