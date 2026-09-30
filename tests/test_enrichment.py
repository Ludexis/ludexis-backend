import uuid
from types import SimpleNamespace

from app.models.archive_entry import ArchiveEntry
from app.models.job_history import JobHistory
from app.providers.metadata_provider import MetadataProvider
from app.schemas.metadata import MetadataDetails, MetadataSearchResult
from app.services.enrichment import EnrichmentService
from app.services.metadata import MetadataService
from app.tasks import job_runner
from app.utils.enums import JobStatus, JobType, MetadataStatus
from tests.test_db import TestingSessionLocal


class CatalogProvider(MetadataProvider):
    """Answers every search with one fixed catalog title."""

    name = "Catalog"
    priority = 1

    def __init__(self, catalog_title: str) -> None:
        self.catalog_title = catalog_title

    def search(self, query, limit=20):
        return [MetadataSearchResult(provider=self.name, provider_id="42", title=self.catalog_title)]

    def get_details(self, external_id):
        return MetadataDetails(
            provider=self.name,
            provider_id=external_id,
            title=self.catalog_title,
            description="From the catalog",
            genres=["Adventure"],
            developers=[f"Studio {uuid.uuid4().hex[:8]}"],
        )

    def download_artwork(self, external_id):
        return None


def make_entry(db, title: str) -> ArchiveEntry:
    entry = ArchiveEntry(
        title=title,
        file_path=f"/library/{uuid.uuid4()}.zip",
        metadata_status=MetadataStatus.UNMATCHED,
    )
    db.add(entry)
    db.commit()
    return entry


def test_new_entry_is_matched_and_enriched():
    db = TestingSessionLocal()
    entry = make_entry(db, f"Harbor Lights {uuid.uuid4().hex[:6]}")
    service = EnrichmentService(MetadataService(providers=[CatalogProvider(entry.title)]))

    stats = service.enrich(db, [entry.id])

    db.refresh(entry)
    assert stats["matched"] == 1
    assert entry.metadata_status == MetadataStatus.MATCHED
    assert entry.metadata_source == "Catalog"
    assert entry.description == "From the catalog"
    assert [genre.name for genre in entry.genres] == ["Adventure"]
    assert len(entry.developers) == 1
    db.close()


def test_weak_candidate_is_not_recorded_as_source():
    db = TestingSessionLocal()
    entry = make_entry(db, "Completely Different Name")
    service = EnrichmentService(MetadataService(providers=[CatalogProvider("Unrelated Catalog Game")]))

    stats = service.enrich(db, [entry.id])

    db.refresh(entry)
    assert stats["unmatched"] == 1
    assert entry.metadata_status == MetadataStatus.UNMATCHED
    assert entry.metadata_source is None
    assert entry.last_metadata_refresh is not None
    db.close()


def test_scheduled_candidates_skip_entries_that_already_failed():
    db = TestingSessionLocal()
    entry = make_entry(db, "Never Matched")
    MetadataService(providers=[CatalogProvider("Something Else Entirely")]).auto_match_archive(db, entry)

    candidates = MetadataService(providers=[]).enrichment_candidates(db)

    assert entry.id not in {candidate.id for candidate in candidates}
    db.close()


def test_run_job_records_progress_and_retry_count(monkeypatch):
    monkeypatch.setattr(job_runner, "SessionLocal", TestingSessionLocal)
    db = TestingSessionLocal()
    job = JobHistory(job_type=JobType.METADATA_REFRESH, status=JobStatus.PENDING, progress=0)
    db.add(job)
    db.commit()
    seen = []

    def work(session, report, job_id):
        for done in range(1, 5):
            report(done, 4)
            seen.append(session.get(JobHistory, job_id).progress)
        return {"processed": 4, "cancelled": False, "ids": ["x"]}

    result = job_runner.run_job(SimpleNamespace(request=SimpleNamespace(retries=2)), job.id, "Test job", work)

    db.refresh(job)
    assert seen == [25, 50, 75, 100]
    assert job.status == JobStatus.SUCCESS
    assert job.retry_count == 2
    assert result == "Test job completed: {'processed': 4}"
    db.close()


def test_title_similarity():
    from app.services.metadata import PARTIAL_THRESHOLD, title_similarity

    assert title_similarity("SomeGameTitle", "Some Game Title") == 1.0
    assert title_similarity("The Long Road", "The Long Road: Redux") >= PARTIAL_THRESHOLD
    assert title_similarity("No Peace", "Snow Peace") < PARTIAL_THRESHOLD
