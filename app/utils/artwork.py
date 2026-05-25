import uuid
from enum import Enum
from pathlib import Path


class ArtworkType(str, Enum):
    COVER = "cover"
    BANNER = "banner"
    LOGO = "logo"
    SCREENSHOT = "screenshot"

    @classmethod
    def list_values(cls) -> list[str]:
        return [member.value for member in cls]


def build_artwork_relative_path(entry_id: str, artwork_type: ArtworkType, original_filename: str) -> str:
    safe_name = Path(original_filename).name
    suffix = Path(safe_name).suffix.lower() or ".png"
    filename = f"{uuid.uuid4().hex}{suffix}"
    return str(Path(entry_id) / artwork_type.value / filename)


def is_allowed_artwork_mime_type(content_type: str, allowed_types: list[str]) -> bool:
    return content_type.lower() in {allowed.lower() for allowed in allowed_types}
