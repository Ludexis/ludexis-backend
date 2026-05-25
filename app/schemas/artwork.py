from pydantic import BaseModel

from app.utils.artwork import ArtworkType


class ArtworkUploadResponse(BaseModel):
    archive_entry_id: str
    artwork_type: ArtworkType
    file_path: str
    screenshot_id: str | None = None
    caption: str | None = None


class ArtworkReplaceResponse(ArtworkUploadResponse):
    pass


class ArtworkDeleteResponse(BaseModel):
    archive_entry_id: str | None = None
    artwork_type: ArtworkType | None = None
    screenshot_id: str | None = None
    deleted: bool = False


class ArtworkMissingResponse(BaseModel):
    archive_entry_id: str
    title: str
    missing_types: list[ArtworkType]


class ArtworkValidationResult(BaseModel):
    archive_entry_id: str
    title: str
    verification_status: str
    missing_types: list[ArtworkType]
