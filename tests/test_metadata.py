from app.services.metadata import MetadataService
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import (
    MetadataSearchResult,
    MetadataDetails,
)


class FakeProvider(MetadataProvider):
    name = "Fake"
    priority = 1

    def search(self, query, limit=20):
        return [
            MetadataSearchResult(
                provider="Fake",
                provider_id="1",
                title="Portal 2",
                summary="Test",
            )
        ]

    def get_details(self, external_id):
        return MetadataDetails(
            provider="Fake",
            provider_id="1",
            title="Portal 2",
            description="Test Game",
            genres=[],
            developers=[],
            publishers=[],
            tags=[],
            cover_urls=[],
            banner_urls=[],
            logo_urls=[],
            artwork_urls=[],
        )

    def download_artwork(self, external_id):
        return None


def test_search_returns_results():
    service = MetadataService(
        providers=[FakeProvider()]
    )
    results = service.search(
        "Portal"
    )
    assert len(results) == 1
    assert results[0].title == "Portal 2"


def test_auto_match_success():
    service = MetadataService(
        providers=[FakeProvider()]
    )
    match, score = service.auto_match(
        "Portal 2"
    )
    assert match is not None
    assert match.title == "Portal 2"
    assert score > 0.9


class EmptyProvider(FakeProvider):
    def search(self, query, limit=20):
        return []
    
def test_auto_match_no_results():
    service = MetadataService(
        providers=[EmptyProvider()]
    )
    match, score = service.auto_match(
        "SomeRandomGame"
    )
    assert match is None
    assert score == 0

def test_get_details():
    service = MetadataService(
        providers=[FakeProvider()]
    )
    details = service.get_details(
        "Fake",
        "1",
    )
    assert details is not None
    assert details.title == "Portal 2"

def test_get_details_unknown_provider():
    service = MetadataService(
        providers=[FakeProvider()]
    )
    details = service.get_details(
        "Unknown",
        "1",
    )
    assert details is None