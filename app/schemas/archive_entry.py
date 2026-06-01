from datetime import date

from pydantic import BaseModel, computed_field

from app.schemas.base import TimestampedModel
from app.schemas.collection import CollectionRead
from app.schemas.developer import DeveloperRead
from app.schemas.franchise import FranchiseRead
from app.schemas.publisher import PublisherRead
from app.schemas.tag import TagRead
from app.utils.enums import MetadataStatus, VerificationStatus


class ArchiveEntryReference(BaseModel):
    id: str
    title: str

    model_config = {
        "from_attributes": True,
    }


class ArchiveEntryBase(BaseModel):
    title: str
    description: str | None = None
    version: str | None = None
    engine: str | None = None
    release_date: date | None = None
    archive_type: str | None = None
    file_path: str
    storage_device: str | None = None
    cover_path: str | None = None
    banner_path: str | None = None
    logo_path: str | None = None
    metadata_status: MetadataStatus = MetadataStatus.UNMATCHED
    metadata_source: str | None = None
    metadata_source_code: str | None = None
    last_metadata_refresh: str | None = None
    last_verified: str | None = None
    verification_status: VerificationStatus = VerificationStatus.UNKNOWN
    parent_series_id: str | None = None
    franchise_id: str | None = None
    related_entry_ids: list[str] = []


class ArchiveEntryCreate(ArchiveEntryBase):
    tag_ids: list[str] = []
    developer_ids: list[str] = []
    publisher_ids: list[str] = []
    collection_ids: list[str] = []


class ArchiveEntryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    version: str | None = None
    engine: str | None = None
    release_date: date | None = None
    archive_type: str | None = None
    file_path: str | None = None
    storage_device: str | None = None
    cover_path: str | None = None
    banner_path: str | None = None
    logo_path: str | None = None
    metadata_status: MetadataStatus | None = None
    metadata_source: str | None = None
    metadata_source_code: str | None = None
    last_metadata_refresh: str | None = None
    last_verified: str | None = None
    verification_status: VerificationStatus | None = None
    parent_series_id: str | None = None
    franchise_id: str | None = None
    tag_ids: list[str] | None = None
    developer_ids: list[str] | None = None
    publisher_ids: list[str] | None = None
    collection_ids: list[str] | None = None
    related_entry_ids: list[str] | None = None


class ArchiveEntryRead(ArchiveEntryBase, TimestampedModel):
    id: str

    tags: list[TagRead] = []
    developers: list[DeveloperRead] = []
    publishers: list[PublisherRead] = []
    collections: list[CollectionRead] = []

    franchise: FranchiseRead | None = None
    parent_series: ArchiveEntryReference | None = None
    related_entries: list[ArchiveEntryReference] = []

    @computed_field
    @property
    def tag_ids(self) -> list[str]:
        return [tag.id for tag in self.tags]


    @computed_field
    @property
    def developer_ids(self) -> list[str]:
        return [dev.id for dev in self.developers]


    @computed_field
    @property
    def publisher_ids(self) -> list[str]:
        return [pub.id for pub in self.publishers]


    @computed_field
    @property
    def collection_ids(self) -> list[str]:
        return [col.id for col in self.collections]

    model_config = {
        "from_attributes": True,
    }
