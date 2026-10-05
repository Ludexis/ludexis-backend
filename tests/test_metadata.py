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

class CatalogProvider(MetadataProvider):
    def __init__(self, name, priority, games):
        self.name = name
        self.priority = priority
        self.games = {game.provider_id: game for game in games}

    def search(self, query, limit=20):
        return [MetadataSearchResult(provider=self.name, provider_id=game.provider_id, title=game.title) for game in self.games.values()]

    def get_details(self, external_id):
        return self.games.get(external_id)

    def download_artwork(self, external_id):
        return None


def test_merged_details_fill_gaps_from_other_providers():
    from datetime import date

    vn = MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow", release_date=date(2021, 5, 4),
                         developers=["Pond Works"], tags=["Drama"], cover_urls=["vndb-cover"])
    game = MetadataDetails(provider="IGDB", provider_id="7", title="Quiet Meadow", release_date=date(2021, 6, 1),
                           developers=["POND WORKS"], genres=["Visual Novel"], franchises=["Meadow"], cover_urls=["igdb-cover"])
    service = MetadataService(providers=[CatalogProvider("VNDB", 5, [vn]), CatalogProvider("IGDB", 10, [game])])

    merged = service.get_merged_details("quiet meadow v0.4", "VNDB", "v1")

    assert merged.provider == "VNDB"
    assert merged.developers == ["Pond Works"]
    assert merged.genres == ["Visual Novel"]
    assert merged.franchises == ["Meadow"]
    assert merged.cover_urls == ["vndb-cover", "igdb-cover"]


def test_merged_details_skip_a_same_name_game_from_another_year():
    from datetime import date

    vn = MetadataDetails(provider="VNDB", provider_id="v1", title="Quiet Meadow", release_date=date(2021, 5, 4))
    remake = MetadataDetails(provider="IGDB", provider_id="7", title="Quiet Meadow", release_date=date(2015, 1, 1), franchises=["Other"])
    service = MetadataService(providers=[CatalogProvider("VNDB", 5, [vn]), CatalogProvider("IGDB", 10, [remake])])

    assert service.get_merged_details("Quiet Meadow", "VNDB", "v1").franchises == []
