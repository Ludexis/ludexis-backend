import uuid
from unittest.mock import patch

import pytest

from app.models.archive_entry import ArchiveEntry
from app.schemas.metadata import MetadataDetails
from app.services.metadata import MetadataService
from app.services.metadata_conflict import MetadataConflictResolver
from app.utils.normalization import company_key
from tests.test_db import TestingSessionLocal


@pytest.mark.parametrize("left, right", [
    ("SEGA", "Sega"),
    ("The Creative Assembly", "CREATIVE ASSEMBLY"),
    ("Wube Software LTD.", "Wube Software"),
    ("Valve Corporation", "Valve"),
    ("Pond & Reed Inc.", "Pond and Reed"),
])
def test_spellings_of_one_company_share_a_key(left, right):
    assert company_key(left) == company_key(right)


@pytest.mark.parametrize("left, right", [
    ("Electronic Arts", "Electronic"),
    ("The Pond", "Pond Works"),
])
def test_different_companies_keep_different_keys(left, right):
    assert company_key(left) != company_key(right)


def test_one_word_names_are_not_stripped_away():
    assert company_key("The") == "the"
    assert company_key("Co") == "co"


def test_merge_keeps_one_spelling_per_company():
    merged = MetadataConflictResolver()._merge_companies(["Sega", "Pond Works"], ["SEGA", "pond works ltd"])
    assert merged == ["Pond Works", "Sega"]


def test_refresh_links_spellings_of_one_company_to_one_record():
    db = TestingSessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        first = ArchiveEntry(title=f"First {suffix}", file_path=f"/games/a-{suffix}", metadata_source="VNDB", metadata_source_code="v1")
        second = ArchiveEntry(title=f"Second {suffix}", file_path=f"/games/b-{suffix}", metadata_source="VNDB", metadata_source_code="v2")
        db.add_all([first, second])
        db.commit()

        service = MetadataService()
        for archive, developers in (
            (first, [f"Reedwork {suffix}", f"REEDWORK {suffix}"]),
            (second, [f"The Reedwork {suffix} Ltd."]),
        ):
            details = MetadataDetails(provider="VNDB", provider_id="v", title="x", developers=developers, publishers=developers)
            with patch.object(service, "get_merged_details", return_value=details):
                assert service.refresh_archive(db, archive)

        assert len(first.developers) == 1
        assert first.developers[0].name == f"Reedwork {suffix}"
        assert second.developers[0].id == first.developers[0].id
        assert second.publishers[0].id == first.publishers[0].id
    finally:
        db.close()
