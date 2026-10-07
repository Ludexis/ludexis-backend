import datetime
import uuid

from fastapi.testclient import TestClient

from app.models.archive_entry import ArchiveEntry
from app.models.collection import Collection
from app.models.genre import Genre
from main import app
from tests.test_db import TestingSessionLocal

client = TestClient(app)


def auth_headers() -> dict:
    token = client.post("/api/auth/login", json={"username": "admin", "password": "Admin123!"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def seed_entries() -> tuple[str, str, str, str]:
    """Three entries sharing a unique word, one genre and one collection; returns (word, genre, collection, collection id)."""
    word = uuid.uuid4().hex[:12]
    db = TestingSessionLocal()
    genre = Genre(name=f"Genre {word}")
    collection = Collection(name=f"Collection {word}")
    specs = [
        ("b", datetime.date(2001, 1, 1), 300),
        ("A", None, 100),
        ("c", datetime.date(1999, 1, 1), 200),
    ]
    for prefix, released, size in specs:
        entry = ArchiveEntry(title=f"{prefix} {word}", file_path=f"/games/{prefix}-{word}.zip", release_date=released, file_size=size)
        entry.genres.append(genre)
        if prefix != "c":
            entry.collections.append(collection)
        db.add(entry)
    db.commit()
    collection_id = collection.id
    db.close()
    return word, f"Genre {word}", f"Collection {word}", collection_id


def titles(response) -> list[str]:
    return [entry["title"].split()[0] for entry in response.json()]


def test_search_sorts_counts_and_returns_genres():
    word, genre, collection, collection_id = seed_entries()
    headers = auth_headers()

    by_title = client.get("/api/search/", params={"q": word}, headers=headers)
    assert titles(by_title) == ["A", "b", "c"]
    assert by_title.headers["X-Total-Count"] == "3"
    assert by_title.json()[0]["genres"] == [genre]

    by_size = client.get("/api/search/", params={"q": word, "sort": "-file_size"}, headers=headers)
    assert titles(by_size) == ["b", "c", "A"]

    # Entries without a release date sort last in both directions.
    assert titles(client.get("/api/search/", params={"q": word, "sort": "release_date"}, headers=headers))[-1] == "A"
    assert titles(client.get("/api/search/", params={"q": word, "sort": "-release_date"}, headers=headers))[-1] == "A"

    page = client.get("/api/search/", params={"q": word, "limit": 1, "offset": 1}, headers=headers)
    assert titles(page) == ["b"]
    assert page.headers["X-Total-Count"] == "3"

    in_collection = client.get("/api/search/", params={"collection": collection}, headers=headers)
    assert titles(in_collection) == ["A", "b"]
    assert in_collection.headers["X-Total-Count"] == "2"
    by_id = client.get("/api/search/", params={"collection_id": collection_id}, headers=headers)
    assert titles(by_id) == ["A", "b"]


def test_search_rejects_unknown_sort():
    response = client.get("/api/search/", params={"sort": "file_path"}, headers=auth_headers())
    assert response.status_code == 422


def test_genres_lists_names_with_entry_counts():
    _, genre, _, _ = seed_entries()
    genres = client.get("/api/genres/", headers=auth_headers()).json()
    assert {"name": genre, "entry_count": 3} in genres
