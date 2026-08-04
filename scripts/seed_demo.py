"""Idempotent demo dataset seeder for Ludexis.

Populates a fresh deployment with an admin account, demo roles and
permissions, a demo library, and a set of archive entries with generated
artwork so the UI has meaningful content on first boot.

Designed to run inside the backend container during startup or against a
development database. Safe to run repeatedly.
"""

import os
import struct
import sys
import uuid
import zlib
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.archive_entry import ArchiveEntry
from app.models.collection import Collection
from app.models.developer import Developer
from app.models.franchise import Franchise
from app.models.library import Library
from app.models.permission import Permission
from app.models.publisher import Publisher
from app.models.role import Role
from app.models.screenshot import Screenshot
from app.models.tag import Tag
from app.models.user import User
from app.utils.enums import MetadataStatus, PermissionName, RoleName, VerificationStatus


def make_png(width: int, height: int, rgb: tuple[int, int, int]) -> bytes:
    """Create a solid-colour PNG without third-party image libraries."""
    def chunk(tag: bytes, data: bytes) -> bytes:
        payload = tag + data
        return (
            struct.pack(">I", len(data))
            + payload
            + struct.pack(">I", zlib.crc32(payload) & 0xFFFFFFFF)
        )

    row = b"\x00" + bytes(rgb) * width
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(row * height))
        + chunk(b"IEND", b"")
    )


def write_artwork(relative_path: str, width: int, height: int, rgb: tuple[int, int, int]) -> str:
    destination = os.path.join(settings.ARTWORK_STORAGE_PATH, relative_path)
    os.makedirs(os.path.dirname(destination), exist_ok=True)
    with open(destination, "wb") as handle:
        handle.write(make_png(width, height, rgb))
    return relative_path


def seed(db) -> list[str]:
    created: list[str] = []
    now = datetime.now(timezone.utc)

    for name in PermissionName:
        existing = db.query(Permission).filter_by(name=name.value).first()
        if existing is None:
            db.add(
                Permission(
                    name=name.value,
                    description="Allows " + name.value.lower().replace("_", " ") + " access",
                )
            )
            created.append(f"permission:{name.value}")

    role_defs = [
        (RoleName.ADMINISTRATOR.value, "Full administrative access"),
        (RoleName.MODERATOR.value, "Moderation and metadata editing"),
        (RoleName.USER.value, "Standard user access"),
        (RoleName.READ_ONLY.value, "Read-only access"),
    ]
    roles: dict[str, Role] = {}
    for name, description in role_defs:
        role = db.query(Role).filter_by(name=name).first()
        if role is None:
            role = Role(name=name, description=description)
            db.add(role)
            created.append(f"role:{name}")
        roles[name] = role

    db.flush()

    admin_role = roles[RoleName.ADMINISTRATOR.value]
    for permission in db.query(Permission).all():
        if permission not in admin_role.permissions:
            admin_role.permissions.append(permission)

    admin = db.query(User).filter_by(username="admin").first()
    if admin is None:
        admin = User(
            username="admin",
            email="admin@example.com",
            hashed_password=hash_password("admin"),
            is_active=True,
            is_superuser=True,
        )
        admin.roles.append(admin_role)
        db.add(admin)
        created.append("user:admin")

    library = db.query(Library).filter_by(name="Demo Library").first()
    if library is None:
        library = Library(name="Demo Library", path="/demo/library", enabled=True)
        db.add(library)
        created.append("library:Demo Library")
    db.flush()
    library_id = library.id

    tags: dict[str, Tag] = {}
    for name, color in [
        ("Retro", "#ffcc00"),
        ("FPS", "#ff6b6b"),
        ("RPG", "#6b8cff"),
        ("Strategy", "#6bff9e"),
        ("Indie", "#ff9e6b"),
        ("Horror", "#c06bff"),
        ("Platformer", "#6bfff0"),
        ("Puzzle", "#ffe06b"),
        ("Sci-Fi", "#8e6bff"),
        ("Fantasy", "#ff6bd4"),
    ]:
        tag = db.query(Tag).filter_by(name=name).first()
        if tag is None:
            tag = Tag(name=name, color=color, description=f"Games tagged {name}")
            db.add(tag)
            created.append(f"tag:{name}")
        tags[name] = tag

    developers: dict[str, Developer] = {}
    for name in [
        "id Software",
        "Valve",
        "Nintendo",
        "Rockstar",
        "BioWare",
        "CD Projekt Red",
        "Bethesda Game Studios",
        "Extremely OK Games",
    ]:
        developer = db.query(Developer).filter_by(name=name).first()
        if developer is None:
            developer = Developer(name=name, description=f"Game studio {name}")
            db.add(developer)
            created.append(f"developer:{name}")
        developers[name] = developer

    publishers: dict[str, Publisher] = {}
    for name in ["Bethesda", "Electronic Arts", "Activision", "Ubisoft"]:
        publisher = db.query(Publisher).filter_by(name=name).first()
        if publisher is None:
            publisher = Publisher(name=name, description=f"Game publisher {name}")
            db.add(publisher)
            created.append(f"publisher:{name}")
        publishers[name] = publisher

    franchises: dict[str, Franchise] = {}
    for name in ["Doom", "Half-Life", "The Elder Scrolls", "Mass Effect"]:
        franchise = db.query(Franchise).filter_by(name=name).first()
        if franchise is None:
            franchise = Franchise(name=name, description=f"{name} series")
            db.add(franchise)
            created.append(f"franchise:{name}")
        franchises[name] = franchise

    db.flush()

    entries_spec = [
        {
            "title": "Doom (1993)",
            "version": "v1.9",
            "engine": "id Tech 1",
            "release_date": date(1993, 12, 10),
            "archive_type": "ZIP",
            "file_size": 12_345_678,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.98,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": "Doom",
            "developers": ["id Software"],
            "publishers": ["Activision"],
            "tags": ["Retro", "FPS", "Sci-Fi"],
            "color": (166, 30, 30),
        },
        {
            "title": "Doom II: Hell on Earth",
            "version": "v1.9",
            "engine": "id Tech 1",
            "release_date": date(1994, 10, 10),
            "archive_type": "ZIP",
            "file_size": 16_890_123,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.95,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": "Doom",
            "developers": ["id Software"],
            "publishers": ["Activision"],
            "tags": ["FPS", "Sci-Fi", "Horror"],
            "color": (139, 20, 20),
        },
        {
            "title": "Half-Life",
            "version": "v1.1.1.0",
            "engine": "GoldSrc",
            "release_date": date(1998, 11, 19),
            "archive_type": "7Z",
            "file_size": 42_501_234,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.96,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": "Half-Life",
            "developers": ["Valve"],
            "publishers": ["Activision"],
            "tags": ["FPS", "Sci-Fi"],
            "color": (40, 40, 120),
        },
        {
            "title": "Half-Life 2",
            "version": "v5135",
            "engine": "Source",
            "release_date": date(2004, 11, 16),
            "archive_type": "7Z",
            "file_size": 6_512_000_000,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.92,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": "Half-Life",
            "developers": ["Valve"],
            "publishers": ["Electronic Arts"],
            "tags": ["FPS", "Sci-Fi", "Strategy"],
            "color": (60, 60, 140),
        },
        {
            "title": "The Elder Scrolls V: Skyrim",
            "version": "v1.9.32",
            "engine": "Creation Engine",
            "release_date": date(2011, 11, 11),
            "archive_type": "7Z",
            "file_size": 12_100_000_000,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.90,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": "The Elder Scrolls",
            "developers": ["Bethesda Game Studios"],
            "publishers": ["Bethesda"],
            "tags": ["RPG", "Fantasy"],
            "color": (70, 70, 70),
        },
        {
            "title": "Mass Effect 2",
            "version": "v1.02",
            "engine": "Unreal Engine 3",
            "release_date": date(2010, 1, 26),
            "archive_type": "ISO",
            "file_size": 15_400_000_000,
            "metadata_status": MetadataStatus.PARTIAL,
            "metadata_confidence": 0.78,
            "verification_status": VerificationStatus.UNKNOWN,
            "franchise": "Mass Effect",
            "developers": ["BioWare"],
            "publishers": ["Electronic Arts"],
            "tags": ["RPG", "Sci-Fi"],
            "color": (60, 40, 90),
        },
        {
            "title": "The Witcher 3: Wild Hunt",
            "version": "v1.32",
            "engine": "REDengine 3",
            "release_date": date(2015, 5, 19),
            "archive_type": "7Z",
            "file_size": 29_000_000_000,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.88,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": None,
            "developers": ["CD Projekt Red"],
            "publishers": ["Electronic Arts"],
            "tags": ["RPG", "Fantasy"],
            "color": (90, 60, 30),
        },
        {
            "title": "Portal 2",
            "version": "v2.0.1",
            "engine": "Source",
            "release_date": date(2011, 4, 19),
            "archive_type": "7Z",
            "file_size": 8_200_000_000,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.93,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": None,
            "developers": ["Valve"],
            "publishers": ["Electronic Arts"],
            "tags": ["Puzzle", "Sci-Fi"],
            "color": (30, 90, 90),
        },
        {
            "title": "Super Mario Bros.",
            "version": "World 1-1",
            "engine": None,
            "release_date": date(1985, 9, 13),
            "archive_type": "ROM",
            "file_size": 40_960,
            "metadata_status": MetadataStatus.MANUAL,
            "metadata_confidence": 0.0,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": None,
            "developers": ["Nintendo"],
            "publishers": ["Nintendo"],
            "tags": ["Platformer", "Retro"],
            "color": (180, 30, 30),
        },
        {
            "title": "Celeste",
            "version": "v1.4.0.0",
            "engine": "MonoGame",
            "release_date": date(2018, 1, 25),
            "archive_type": "7Z",
            "file_size": 320_000_000,
            "metadata_status": MetadataStatus.MATCHED,
            "metadata_confidence": 0.85,
            "verification_status": VerificationStatus.VERIFIED,
            "franchise": None,
            "developers": ["Extremely OK Games"],
            "publishers": ["Extremely OK Games"],
            "tags": ["Indie", "Platformer", "Puzzle"],
            "color": (50, 90, 160),
        },
    ]

    for spec in entries_spec:
        existing = db.query(ArchiveEntry).filter_by(title=spec["title"]).first()
        if existing is not None:
            continue

        cover_rel = write_artwork(
            f"covers/{uuid.uuid4()}.png", 600, 800, spec["color"]
        )
        entry = ArchiveEntry(
            title=spec["title"],
            description=(
                f"Demo archive entry for {spec['title']}. Seeded as part of the "
                "Ludexis demo dataset."
            ),
            version=spec["version"],
            engine=spec["engine"],
            release_date=spec["release_date"],
            archive_type=spec["archive_type"],
            file_path=f"/demo/library/{spec['title'].replace(' ', '_')}.zip",
            file_size=spec["file_size"],
            storage_device="Demo",
            modified_time=now,
            cover_path=cover_rel,
            metadata_status=spec["metadata_status"],
            metadata_source="Demo Seed",
            metadata_source_code="DEMO",
            metadata_confidence=spec["metadata_confidence"],
            last_metadata_refresh=now,
            last_verified=now,
            verification_status=spec["verification_status"],
            franchise_id=franchises[spec["franchise"]].id if spec.get("franchise") else None,
            library_id=library_id,
        )
        for tag_name in spec["tags"]:
            entry.tags.append(tags[tag_name])
        for developer_name in spec.get("developers", []):
            entry.developers.append(developers[developer_name])
        for publisher_name in spec.get("publishers", []):
            entry.publishers.append(publishers[publisher_name])
        db.add(entry)
        db.flush()

        for index in range(2):
            shot_rel = write_artwork(
                f"screenshots/{uuid.uuid4()}.png",
                1280,
                720,
                tuple(min(255, channel + index * 40) for channel in spec["color"]),
            )
            db.add(
                Screenshot(
                    archive_entry_id=entry.id,
                    file_path=shot_rel,
                    caption=f"{spec['title']} in-game screenshot {index + 1}",
                )
            )
        created.append(f"archive_entry:{spec['title']}")

    collection_specs = [
        {
            "name": "FPS Classics",
            "description": "First-person shooters that defined the genre",
            "titles": ["Doom (1993)", "Doom II: Hell on Earth", "Half-Life", "Half-Life 2"],
            "color": (120, 40, 40),
        },
        {
            "name": "Story-Rich RPGs",
            "description": "Role-playing games with unforgettable narratives",
            "titles": [
                "The Elder Scrolls V: Skyrim",
                "Mass Effect 2",
                "The Witcher 3: Wild Hunt",
            ],
            "color": (50, 50, 120),
        },
        {
            "name": "Retro Essentials",
            "description": "Timeless classics worth preserving",
            "titles": ["Super Mario Bros.", "Doom (1993)", "Celeste"],
            "color": (150, 120, 30),
        },
    ]
    for spec in collection_specs:
        existing = db.query(Collection).filter_by(name=spec["name"]).first()
        if existing is not None:
            continue
        cover_rel = write_artwork(
            f"covers/{uuid.uuid4()}.png", 800, 450, spec["color"]
        )
        collection = Collection(
            name=spec["name"],
            description=spec["description"],
            cover_path=cover_rel,
            visibility="public",
        )
        for title in spec["titles"]:
            entry = db.query(ArchiveEntry).filter_by(title=title).first()
            if entry is not None:
                collection.archive_entries.append(entry)
        db.add(collection)
        created.append(f"collection:{spec['name']}")

    db.commit()
    return created


def main() -> None:
    db = SessionLocal()
    try:
        created = seed(db)
        if created:
            print(f"Demo dataset seeded: {', '.join(created)}")
        else:
            print("Demo dataset already present; nothing to do.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
