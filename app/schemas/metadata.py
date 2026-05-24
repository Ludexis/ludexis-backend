from datetime import date

from pydantic import BaseModel


class MetadataSearchResult(BaseModel):
    provider: str
    provider_id: str
    title: str
    summary: str | None = None
    release_date: date | None = None


class MetadataDetails(BaseModel):
    provider: str
    provider_id: str
    title: str
    description: str | None = None
    release_date: date | None = None
    genres: list[str] = []
    developers: list[str] = []
    publishers: list[str] = []
    tags: list[str] = []
    artwork_urls: list[str] = []
