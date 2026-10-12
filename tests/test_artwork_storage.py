import random
import uuid
from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from app.models.archive_entry import ArchiveEntry
from app.models.screenshot import Screenshot
from app.services.artwork import ArtworkService
from app.utils.artwork import is_versioned, optimize_artwork
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)


def encoded(image: Image.Image, image_format: str, **options) -> bytes:
    buffer = BytesIO()
    image.save(buffer, image_format, **options)
    return buffer.getvalue()


def noisy(width: int, height: int, mode: str = "RGB") -> Image.Image:
    # Detail like a real picture, so lossy WebP has something to save on.
    rng = random.Random(width * height)
    return Image.frombytes(mode, (width, height), rng.randbytes(width * height * len(mode)))


def opened(contents: bytes) -> Image.Image:
    return Image.open(BytesIO(contents))


def visible_pixels(image: Image.Image) -> list:
    # Lossless WebP keeps every visible pixel; the colour under a fully transparent one is not kept.
    return [pixel if pixel[3] else None for pixel in image.convert("RGBA").getdata()]


def test_a_wide_banner_becomes_a_1920_px_webp_with_a_versioned_name():
    path, contents = optimize_artwork("banners/e1.png", encoded(noisy(3840, 1240), "PNG"))

    assert path.startswith("banners/e1.v") and path.endswith(".webp") and is_versioned(path)
    assert (opened(contents).format, opened(contents).size) == ("WEBP", (1920, 620))


def test_screenshots_become_webp_and_logos_lossless_webp():
    shot_path, shot = optimize_artwork("e1/screenshot/a.jpg", encoded(noisy(640, 360), "JPEG", quality=95))
    assert shot_path.endswith(".webp") and opened(shot).size == (640, 360)

    logo = noisy(300, 100, "RGBA")
    logo_path, stored_logo = optimize_artwork("logos/e1.png", encoded(logo, "PNG"))
    assert logo_path.endswith(".webp")
    assert visible_pixels(opened(stored_logo)) == visible_pixels(logo)


def test_covers_keep_their_bytes_and_saving_again_keeps_one_version():
    cover = encoded(noisy(264, 352), "JPEG")
    path, contents = optimize_artwork("covers/e1.jpg", cover)

    assert contents == cover and path.endswith(".jpg") and is_versioned(path)
    assert optimize_artwork(path, cover) == (path, cover)
    assert optimize_artwork("covers/e1.jpg", cover + b"\0")[0] != path


def test_a_wide_avif_banner_becomes_a_1920_px_webp():
    path, contents = optimize_artwork("banners/e1.avif", encoded(noisy(3840, 1240), "AVIF"))

    assert path.endswith(".webp") and (opened(contents).format, opened(contents).size) == ("WEBP", (1920, 620))


def test_webp_and_unreadable_files_are_stored_unchanged():
    webp = encoded(noisy(800, 400), "WEBP")
    assert optimize_artwork("banners/e1.webp", webp)[1] == webp
    assert optimize_artwork("banners/e1.jpg", b"not an image")[1] == b"not an image"


def test_stored_art_is_converted_once_and_versioned_names_are_cached_for_good():
    db = TestingSessionLocal()
    service = ArtworkService()
    old_banner, old_shot = f"banners/{uuid.uuid4()}.png", f"screenshots/{uuid.uuid4()}_1.jpg"
    for path, contents in ((old_banner, encoded(noisy(2400, 800), "PNG")), (old_shot, encoded(noisy(640, 360), "JPEG", quality=95))):
        service.storage.absolute_path(path).parent.mkdir(parents=True, exist_ok=True)
        service.storage.absolute_path(path).write_bytes(contents)
    entry = ArchiveEntry(title="Iron Tide", file_path=f"D:/Tmp/{uuid.uuid4()}.zip", banner_path=old_banner)
    db.add(entry)
    db.flush()
    db.add(Screenshot(archive_entry_id=entry.id, file_path=old_shot))
    db.commit()

    assert service.optimize_stored_artwork(db) >= 2
    db.refresh(entry)
    assert entry.banner_path.endswith(".webp") and service.storage.exists(entry.banner_path)
    assert entry.screenshots[0].file_path.endswith(".webp")
    assert service.optimize_stored_artwork(db) == 0

    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).json()["access_token"]
    cookie = {"Cookie": f"ludexis_access={token}"}
    assert client.get(f"/media/{entry.banner_path}", headers=cookie).headers["cache-control"] == "private, max-age=31536000, immutable"
    assert client.get(f"/media/{old_banner}", headers=cookie).headers["cache-control"] == "private, no-cache"
    db.close()
