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


def test_steamgriddb_art_is_added_for_the_same_game_only():
    from datetime import date
    from unittest.mock import MagicMock, patch

    from app.schemas.metadata import MetadataDetails

    def reply(data):
        response = MagicMock(status_code=200)
        response.json.return_value = {"success": True, "data": data}
        return response

    def fake_get(url, **kwargs):
        if "/search/autocomplete/" in url:
            return reply([
                {"id": 1, "name": "Quiet Meadow 2", "release_date": 1609459200},
                {"id": 2, "name": "Quiet Meadow", "release_date": 946684800},  # 2000: another game
                {"id": 4, "name": "Quiet Meadow", "release_date": 1672531200},  # 2023: close, but not closest
                {"id": 3, "name": "Quiet Meadow", "release_date": 1609459200},  # 2021
            ])
        game_id = url.split("/game/")[1]
        kind = url.split("/v2/")[1].split("/")[0]
        return reply([{"url": f"https://grid.example/{kind}-{game_id}.png"}])

    details = MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow", release_date=date(2021, 5, 4),
                              cover_urls=["https://vndb.example/cover.jpg"])
    with patch("app.services.artwork.SettingsService.steamgriddb_key", return_value="key"), \
            patch("app.services.artwork.restricted_sources_allowed", return_value=False), \
            patch("app.providers.steamgriddb.requests.get", side_effect=fake_get) as get:
        ArtworkService()._add_steamgriddb_art(None, details)

    assert details.cover_urls == ["https://vndb.example/cover.jpg", "https://grid.example/grids-3.png"]
    assert details.banner_urls == ["https://grid.example/heroes-3.png"]
    assert details.logo_urls == ["https://grid.example/logos-3.png"]
    assert get.call_args.kwargs["headers"] == {"Authorization": "Bearer key"}
    # Without restricted sources, art the site flags is left out.
    assert get.call_args.kwargs["params"]["nsfw"] == "false"


def test_steamgriddb_takes_every_rating_with_restricted_sources_allowed():
    from unittest.mock import MagicMock, patch

    from app.schemas.metadata import MetadataDetails

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": [{"id": 3, "name": "Quiet Meadow", "url": "https://grid.example/a.png"}]}
    details = MetadataDetails(provider="IGDB", provider_id="1", title="Quiet Meadow")
    with patch("app.services.artwork.SettingsService.steamgriddb_key", return_value="key"), \
            patch("app.services.artwork.restricted_sources_allowed", return_value=True), \
            patch("app.providers.steamgriddb.requests.get", return_value=response) as get:
        ArtworkService()._add_steamgriddb_art(None, details)

    assert get.call_args.kwargs["params"]["nsfw"] == "any"


def test_steamgriddb_skips_a_same_named_game_from_years_apart():
    from datetime import date
    from unittest.mock import MagicMock, patch

    from app.schemas.metadata import MetadataDetails

    response = MagicMock(status_code=200)
    response.json.return_value = {"data": [{"id": 2, "name": "Quiet Meadow", "release_date": 946684800}]}
    details = MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow", release_date=date(2021, 5, 4))
    with patch("app.services.artwork.SettingsService.steamgriddb_key", return_value="key"), \
            patch("app.services.artwork.restricted_sources_allowed", return_value=False), \
            patch("app.providers.steamgriddb.requests.get", return_value=response) as get:
        ArtworkService()._add_steamgriddb_art(None, details)

    assert get.call_count == 1
    assert details.cover_urls == []


def test_banner_falls_back_to_a_screenshot_of_the_new_match():
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
            return MetadataDetails(
                provider="VNDB", provider_id="v1", title="Quiet Meadow", cover_urls=["tall-small"], artwork_urls=["wide-big"]
            )

    service = ReplacingService()
    service.storage.delete = lambda path: None
    service.storage.save = lambda path, contents: path
    service.replace_entries_artwork(db, [entry.id])
    db.refresh(entry)

    assert entry.banner_path == f"banners/{entry.id}.jpg"
    db.close()


def test_unused_artwork_is_removed_and_referenced_or_fresh_files_kept():
    import os
    import time
    import uuid

    from app.models.archive_entry import ArchiveEntry
    from tests.test_db import TestingSessionLocal

    db = TestingSessionLocal()
    service = ArtworkService()
    kept_path = f"covers/{uuid.uuid4()}.jpg"
    entry = ArchiveEntry(title="Quiet Meadow", file_path=f"D:/Tmp/{uuid.uuid4()}.zip", cover_path=kept_path)
    db.add(entry)
    db.commit()
    stale = service.storage.absolute_path(service.storage.save(f"banners/{uuid.uuid4()}.jpg", b"old"))
    fresh = service.storage.absolute_path(service.storage.save(f"logos/{uuid.uuid4()}.png", b"saving"))
    referenced = service.storage.absolute_path(service.storage.save(kept_path, b"cover"))
    hour_ago = time.time() - 7200
    os.utime(stale, (hour_ago, hour_ago))
    os.utime(referenced, (hour_ago, hour_ago))

    service.garbage_collect_artwork(db)

    assert not stale.exists()
    assert fresh.exists() and referenced.exists()
    db.close()
