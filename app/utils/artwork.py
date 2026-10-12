import hashlib
import re
import uuid
from enum import Enum
from io import BytesIO
from pathlib import Path, PurePosixPath

from PIL import Image

# Stored art is named after its contents, so a changed image gets a new URL and browsers can keep each file for good.
VERSION_PATTERN = re.compile(r"\.v[0-9a-f]{10}$")
WEBP_QUALITY = 85
# A banner never shows wider than one screen.
BANNER_MAX_WIDTH = 1920
# Folders of each kind of art: downloads use "banners/", uploads "<entry>/banner/", deduplicated art "dedup/banner/".
PHOTO_FOLDERS = {"banners", "banner", "franchises", "screenshots", "screenshot"}
BANNER_FOLDERS = {"banners", "banner", "franchises"}
LOGO_FOLDERS = {"logos", "logo"}


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


def is_versioned(relative_path: str) -> bool:
    return bool(VERSION_PATTERN.search(PurePosixPath(relative_path.replace("\\", "/")).stem))


def _to_webp(contents: bytes, folders: set[str]) -> bytes | None:
    """Banners, screenshots and franchise images as lossy WebP, logos as lossless WebP; None leaves the file as it is."""
    logo = bool(folders & LOGO_FOLDERS)
    if not logo and not folders & PHOTO_FOLDERS:
        return None
    try:
        image = Image.open(BytesIO(contents))
        # Art that is already WebP is never encoded twice; GIF and SVG are kept too.
        if image.format not in ("JPEG", "PNG", "AVIF"):
            return None
        image.load()
    except Exception:
        return None
    icc_profile = image.info.get("icc_profile")
    has_alpha = image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info
    image = image.convert("RGBA" if has_alpha else "RGB")
    resized = bool(folders & BANNER_FOLDERS) and image.width > BANNER_MAX_WIDTH
    if resized:
        image = image.resize((BANNER_MAX_WIDTH, round(image.height * BANNER_MAX_WIDTH / image.width)), Image.LANCZOS)
    buffer = BytesIO()
    options = {"lossless": True} if logo else {"quality": WEBP_QUALITY}
    image.save(buffer, "WEBP", icc_profile=icc_profile, **options)
    # A small, already well compressed image can come out larger; it is then kept as it is.
    return buffer.getvalue() if resized or buffer.tell() < len(contents) else None


def optimize_artwork(relative_path: str, contents: bytes) -> tuple[str, bytes]:
    """The name and contents art is stored under. Covers keep their bytes; see _to_webp for the rest."""
    path = PurePosixPath(relative_path.replace("\\", "/"))
    webp = _to_webp(contents, set(path.parts[:-1]))
    if webp is not None:
        contents, path = webp, path.with_suffix(".webp")
    stem = VERSION_PATTERN.sub("", path.stem)
    version = hashlib.sha256(contents).hexdigest()[:10]
    return str(path.with_name(f"{stem}.v{version}{path.suffix}")), contents
