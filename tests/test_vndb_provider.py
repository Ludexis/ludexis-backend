import uuid
from datetime import date
from unittest.mock import MagicMock, patch

import requests

from app.models.archive_entry import ArchiveEntry
from app.models.tag import Tag
from app.providers import vndb
from app.providers.vndb import VNDBProvider
from app.schemas.metadata import MetadataDetails
from app.services.metadata import MetadataService
from tests.test_db import TestingSessionLocal


def response(results):
    mock = MagicMock()
    mock.json.return_value = {"results": results, "more": False}
    return mock


def setup_function():
    VNDBProvider._down_until = 0.0
    VNDBProvider._last_request = 0.0


@patch.object(vndb, "MIN_INTERVAL_SECONDS", 0)
def test_search_parses_results():
    with patch("app.providers.vndb.requests.post", return_value=response([
        {"id": "v100", "title": "Quiet Meadow", "alttitle": None, "released": "2021-05-04"},
        {"id": "v101", "title": "Quiet Meadow 2", "released": "TBA"},
    ])) as post:
        results = VNDBProvider().search("quiet meadow", limit=5)

    assert post.call_args.kwargs["json"]["filters"] == ["search", "=", "quiet meadow"]
    assert [(r.provider, r.provider_id, r.title) for r in results] == [
        ("VNDB", "v100", "Quiet Meadow"), ("VNDB", "v101", "Quiet Meadow 2"),
    ]
    assert results[0].release_date == date(2021, 5, 4)
    assert results[1].release_date is None


@patch.object(vndb, "MIN_INTERVAL_SECONDS", 0)
def test_search_by_developer_narrows_the_filter_and_returns_developers():
    with patch("app.providers.vndb.requests.post", return_value=response([
        {"id": "v100", "title": "Quiet Meadow", "developers": [{"id": "p1", "name": "Lantern Works"}]},
    ])) as post:
        results = VNDBProvider().search("quiet meadow", limit=5, developer="lantern")

    assert post.call_args.kwargs["json"]["filters"] == [
        "and", ["search", "=", "quiet meadow"], ["developer", "=", ["search", "=", "lantern"]],
    ]
    assert results[0].developers == ["Lantern Works"]


@patch.object(vndb, "MIN_INTERVAL_SECONDS", 0)
def test_details_filter_tags_and_strip_markup():
    tags = [{"name": f"Tag {i}", "rating": 3.0 - i * 0.05, "spoiler": 0} for i in range(20)]
    tags += [{"name": "Spoiler", "rating": 3.0, "spoiler": 2}, {"name": "Weak", "rating": 1.0, "spoiler": 0}]
    releases = response([
        {"images": [{"type": "pkgback", "url": "https://t.vndb.org/back.jpg"}, {"type": "pkgfront", "url": "https://t.vndb.org/front.jpg"}]},
    ])
    with patch("app.providers.vndb.requests.post", side_effect=[response([{
        "id": "v100",
        "title": "Quiet Meadow",
        "description": "A [url=https://example.com]small[/url] [b]story[/b].",
        "released": "2021-05",
        "developers": [{"name": "Pond Works"}],
        "tags": tags,
        "image": {"url": "https://t.vndb.org/cv/00/100.jpg"},
        "screenshots": [{"url": "https://t.vndb.org/sf/00/1.jpg"}],
    }]), releases]) as post:
        details = VNDBProvider().get_details("v100")

    assert details.description == "A small story."
    assert details.release_date is None
    assert details.developers == ["Pond Works"]
    assert details.tags == [f"Tag {i}" for i in range(15)]
    # Release package fronts come first: the main image is often a landscape banner.
    assert details.cover_urls == ["https://t.vndb.org/front.jpg", "https://t.vndb.org/cv/00/100.jpg"]
    assert post.call_args.args[0].endswith("/release")
    assert details.artwork_urls == ["https://t.vndb.org/sf/00/1.jpg"]


@patch.object(vndb, "MIN_INTERVAL_SECONDS", 0)
def test_unreachable_vndb_backs_off():
    with patch("app.providers.vndb.requests.post", side_effect=requests.ConnectionError) as post:
        assert VNDBProvider().search("anything") == []
        assert VNDBProvider().search("anything else") == []
    assert post.call_count == 1


def test_refresh_replaces_provider_tags_and_keeps_user_tags():
    db = TestingSessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        user_tag = Tag(name=f"favourite-{suffix}")
        old_provider_tag = Tag(name=f"old-{suffix}", origin="provider")
        archive = ArchiveEntry(title=f"Entry {suffix}", file_path=f"/games/{suffix}", metadata_source="VNDB",
                               metadata_source_code="v1", tags=[user_tag, old_provider_tag])
        db.add(archive)
        db.commit()

        details = MetadataDetails(provider="VNDB", provider_id="v1", title="Entry",
                                  tags=[f"new-{suffix}"], franchises=[f"Saga {suffix}"])
        service = MetadataService()
        with patch.object(service, "get_merged_details", return_value=details):
            assert service.refresh_archive(db, archive)

        assert {tag.name for tag in archive.tags} == {f"favourite-{suffix}", f"new-{suffix}"}
        assert {tag.origin for tag in archive.tags if tag.name.startswith("new-")} == {"provider"}
        assert archive.franchise.name == f"Saga {suffix}"
    finally:
        db.close()
