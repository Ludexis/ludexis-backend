"""Checks against a real folder of game archives.

Set LUDEXIS_SAMPLE_LIBRARY to a folder of archives or game folders to run these; they are skipped otherwise.
Run with `pytest tests/test_sample_library.py -s` to print what the scanner and providers make of each item.
"""
import os
from pathlib import Path

import pytest

from app.core.config import settings
from app.services.metadata import MetadataService
from app.services.scanner import SUPPORTED_ARCHIVE_EXTENSIONS, ScannerService
from app.utils.normalization import NOISE_TOKENS

SAMPLE_LIBRARY = os.environ.get("LUDEXIS_SAMPLE_LIBRARY")

pytestmark = pytest.mark.skipif(
    not SAMPLE_LIBRARY or not Path(SAMPLE_LIBRARY).is_dir(),
    reason="LUDEXIS_SAMPLE_LIBRARY is not set to a folder",
)


def discovered_items():
    return ScannerService()._discover_items(Path(SAMPLE_LIBRARY))


def test_every_top_level_archive_becomes_one_item():
    archives = [
        path for path in Path(SAMPLE_LIBRARY).iterdir()
        if path.is_file() and path.suffix.lower() in SUPPORTED_ARCHIVE_EXTENSIONS
    ]
    items = discovered_items()
    discovered_paths = {item.file_path for item in items}

    assert {str(path.resolve()) for path in archives} <= discovered_paths
    assert len(discovered_paths) == len(items)


def test_titles_are_clean():
    for item in discovered_items():
        print(f"{item.filename!r:70} -> title={item.title!r} version={item.version!r}")
        words = item.title.lower().split()
        assert item.title.strip()
        assert not item.title.lower().endswith(tuple(SUPPORTED_ARCHIVE_EXTENSIONS))
        assert not set(words) & NOISE_TOKENS
        assert "_" not in item.title


@pytest.mark.skipif(not settings.TWITCH_CLIENT_ID, reason="IGDB credentials are not configured")
def test_provider_matching_report():
    service = MetadataService()
    for item in discovered_items():
        match, score = service.auto_match(item.title)
        found = f"{match.provider}:{match.title!r}" if match else "no result"
        print(f"{item.title!r:50} -> {found} score={score:.2f}")
        assert 0.0 <= score <= 1.0
