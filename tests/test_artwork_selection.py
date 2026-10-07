from io import BytesIO

from PIL import Image

from app.services.artwork import ArtworkService


def image(width, height):
    buffer = BytesIO()
    Image.new("RGB", (width, height)).save(buffer, "JPEG")
    return buffer.getvalue()


IMAGES = {
    "wide-big": image(1920, 1080),
    "tall-small": image(264, 352),
    "header-small": image(460, 215),
}


class FakeArtworkService(ArtworkService):
    def _download_artwork_url(self, url):
        return IMAGES[url], ".jpg"


def test_cover_prefers_portrait_over_a_larger_landscape_image():
    service = FakeArtworkService()
    assert service._select_best_url(["wide-big", "tall-small"], "portrait") == "tall-small"


def test_banner_takes_landscape_cover_art_over_a_small_header():
    service = FakeArtworkService()
    candidates = ["header-small", "wide-big"]
    assert service._select_best_url(candidates, "landscape", shape_only=["wide-big"]) == "wide-big"


def test_banner_never_takes_a_portrait_cover():
    service = FakeArtworkService()
    assert service._select_best_url(["tall-small"], "landscape", shape_only=["tall-small"]) is None


def test_replacing_artwork_drops_a_slot_the_new_match_does_not_offer():
    import uuid

    from app.models.archive_entry import ArchiveEntry
    from app.schemas.metadata import MetadataDetails
    from tests.test_db import TestingSessionLocal

    db = TestingSessionLocal()
    entry = ArchiveEntry(title="Quiet Meadow", file_path=f"D:/Tmp/{uuid.uuid4()}.zip", banner_path="banners/old-match.jpg")
    db.add(entry)
    db.commit()

    class ReplacingService(FakeArtworkService):
        def _entry_details(self, entry):
            return MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow", cover_urls=["tall-small"])

    service = ReplacingService()
    service.storage.delete = lambda path: None
    service.storage.save = lambda path, contents: path
    service.replace_entries_artwork(db, [entry.id])
    db.refresh(entry)

    assert entry.cover_path.startswith("covers/")
    assert entry.banner_path is None
    db.close()

