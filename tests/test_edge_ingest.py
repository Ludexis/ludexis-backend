import uuid

from app.models.archive_entry import ArchiveEntry
from app.models.edge_device import EdgeDevice
from app.models.library import Library
from app.services.scanner import ScannerService
from app.utils.enums import LibraryStatus, VerificationStatus
from tests.test_db import TestingSessionLocal


def item(root, name, file_hash=None, size=10):
    return {
        "file_path": f"{root}/{name}", "relative_path": name, "filename": name, "archive_name": name.rsplit(".", 1)[0],
        "folder_name": None, "title": name.rsplit(".", 1)[0], "version": None, "archive_type": "ZIP",
        "file_size": size, "modified_time": "2026-10-01T00:00:00+00:00", "file_hash": file_hash or uuid.uuid4().hex * 2,
    }


def edge_library(db):
    edge = EdgeDevice(name=f"Ingest-{uuid.uuid4().hex[:8]}", token_hash=uuid.uuid4().hex * 2)
    db.add(edge)
    db.flush()
    library = Library(name=f"Ingest-{uuid.uuid4().hex[:8]}", path=f"/media/{uuid.uuid4().hex}", edge_id=edge.id)
    db.add(library)
    db.commit()
    return library


def ingest(db, library, items, **extra):
    return ScannerService().ingest_report(db, library, {"library_id": library.id, "items": items, **extra})


def entries(db, library):
    return db.query(ArchiveEntry).filter(ArchiveEntry.library_id == library.id).order_by(ArchiveEntry.relative_path).all()


def test_a_drive_under_a_new_mount_moves_its_entries_without_new_ones():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        first = [item("/drives/E/Games", "Alpha.zip"), item("/drives/E/Games", "Beta.zip")]
        assert ingest(db, library, first)["created"] == 2

        moved = [{**entry, "file_path": entry["file_path"].replace("/drives/E", "/drives/F")} for entry in first]
        stats = ingest(db, library, moved)

        assert stats["created"] == 0
        assert stats["moved"] == 2
        assert [entry.file_path for entry in entries(db, library)] == ["/drives/F/Games/Alpha.zip", "/drives/F/Games/Beta.zip"]


def test_a_file_left_out_of_the_listing_becomes_missing_and_returns():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        listing = [item("/m/G", "Alpha.zip"), item("/m/G", "Beta.zip")]
        ingest(db, library, listing)

        assert ingest(db, library, listing[:1])["missing"] == 1
        assert {entry.relative_path: entry.verification_status for entry in entries(db, library)}["Beta.zip"] == VerificationStatus.MISSING

        ingest(db, library, listing)
        assert all(entry.verification_status != VerificationStatus.MISSING for entry in entries(db, library))


def test_an_empty_listing_or_an_error_takes_the_library_offline_and_keeps_its_entries():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        ingest(db, library, [item("/m/G", "Alpha.zip")])

        stats = ingest(db, library, [])
        assert stats["offline_libraries"] == [library.name]
        assert library.status == LibraryStatus.OFFLINE.value
        assert entries(db, library)[0].verification_status != VerificationStatus.MISSING

        ingest(db, library, [], error="Drive E: is not mapped")
        assert library.last_error == "Drive E: is not mapped"
        assert len(entries(db, library)) == 1


def test_a_report_never_judges_entries_of_other_libraries():
    with TestingSessionLocal() as db:
        first, second = edge_library(db), edge_library(db)
        shared_hash = "c" * 64
        ingest(db, first, [item("/a", "Copy.zip", shared_hash)])

        # The same archive on another device's drive: the first entry's file is not judged gone from this listing.
        stats = ingest(db, second, [item("/b", "Copy.zip", shared_hash)])

        assert stats["created"] == 1
        assert entries(db, first)[0].file_path == "/a/Copy.zip"


def test_a_library_that_comes_back_keeps_its_hashes_and_counts_new_files_as_pending():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        same, resized, gone = item("/m/G", "Same.zip", "d" * 64), item("/m/G", "Resized.zip", "e" * 64), item("/m/G", "Gone.zip")
        ingest(db, library, [same, resized, gone])
        library.status = LibraryStatus.OFFLINE.value
        db.commit()

        # An automatic scan: nothing hashed, a new and a resized file only counted.
        unhashed = {**same, "file_hash": None, "modified_time": "2026-10-05T00:00:00+00:00"}
        stats = ingest(db, library, [unhashed], pending=["Resized.zip", "New.zip"])

        assert stats["reconnected_libraries"] == [library.name]
        assert stats["created"] == 0
        assert stats["missing"] == 1
        assert library.status == LibraryStatus.ONLINE.value
        assert library.pending_changes == 2
        by_name = {entry.relative_path: entry for entry in entries(db, library)}
        assert by_name["Same.zip"].file_hash == "d" * 64
        assert by_name["Resized.zip"].verification_status != VerificationStatus.MISSING
        assert by_name["Gone.zip"].verification_status == VerificationStatus.MISSING

        # The scan the user then starts stores them and clears the count.
        stats = ingest(db, library, [unhashed, {**resized, "file_size": 20}, item("/m/G", "New.zip")])
        assert stats["created"] == 1
        assert library.pending_changes == 0


def test_a_listing_of_only_pending_files_does_not_take_the_library_offline():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        ingest(db, library, [item("/m/G", "Alpha.zip")])

        ingest(db, library, [], pending=["Alpha.zip"])

        assert library.status == LibraryStatus.ONLINE.value
        assert entries(db, library)[0].verification_status != VerificationStatus.MISSING


def test_the_server_scan_leaves_edge_libraries_alone():
    with TestingSessionLocal() as db:
        library = edge_library(db)
        ingest(db, library, [item("/m/G", "Alpha.zip")])

        ScannerService().scan_incremental(db, library_id=library.id)

        assert library.status == LibraryStatus.ONLINE.value
        assert entries(db, library)[0].verification_status != VerificationStatus.MISSING
