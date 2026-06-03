from pathlib import Path
import requests
from fastapi import UploadFile
from sqlalchemy.orm import Session
from PIL import Image

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.models.screenshot import Screenshot
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.screenshot import ScreenshotRepository
from app.services.storage import StorageService
from app.services.metadata import MetadataService
from app.utils.artwork import ArtworkType, build_artwork_relative_path, is_allowed_artwork_mime_type
from app.utils.enums import VerificationStatus


class ArtworkService:
    def __init__(self) -> None:
        self.entry_repo = ArchiveEntryRepository()
        self.screenshot_repo = ScreenshotRepository()
        self.storage = StorageService()
        self.metadata_service = MetadataService()

    def _read_file(self, file: UploadFile) -> bytes:
        file.file.seek(0)
        contents = file.file.read()
        if not contents:
            raise ValueError("Artwork file is empty")
        if not is_allowed_artwork_mime_type(file.content_type or "", settings.ALLOWED_ARTWORK_MIME_TYPES):
            raise ValueError("Unsupported artwork file type")
        max_size = settings.MAX_ARTWORK_SIZE_MB * 1024 * 1024
        if len(contents) > max_size:
            raise ValueError(f"Artwork file exceeds maximum size of {settings.MAX_ARTWORK_SIZE_MB} MB")
        return contents
    
    def _download_artwork_url(self, url: str,) -> tuple[bytes, str]:
        response = requests.get(
            url,
            timeout=30,
        )
        response.raise_for_status()
        content_type = (
            response.headers.get(
                "content-type",
                ""
            )
            .split(";")[0]
            .strip()
            .lower()
        )

        if not is_allowed_artwork_mime_type(
            content_type,
            settings.ALLOWED_ARTWORK_MIME_TYPES,
        ):
            raise ValueError(
                f"Unsupported artwork type: {content_type}"
            )
        contents = response.content
        max_size = (
            settings.MAX_ARTWORK_SIZE_MB
            * 1024
            * 1024
        )
        if len(contents) > max_size:
            raise ValueError(
                f"Artwork exceeds maximum size of "
                f"{settings.MAX_ARTWORK_SIZE_MB} MB"
            )

        extension_map = {
            "image/jpeg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
        }

        extension = (
            extension_map.get(
                content_type,
                ".jpg",
            )
        )
        return contents, extension
    
    def _score_artwork_url(self, url: str,) -> int:
        url = url.lower()
        score = 0
        if "images.igdb.com" in url:
            score += 50
        if "t_cover_big" in url:
            score += 100
        if "t_1080p" in url:
            score += 80
        if "header" in url:
            score += 40
        if "capsule" in url:
            score += 10
        return score

    def _select_best_cover(self, artwork_urls: list[str],) -> str | None:
        if not artwork_urls:
            return None
        ranked = sorted(
            artwork_urls,
            key=self._score_artwork_url,
            reverse=True,
        )
        return ranked[0]

    def auto_download_cover(self, db: Session, archive_entry_id: str, force: bool = False,) -> bool:
        entry = self.entry_repo.get_active(
            db,
            archive_entry_id,
        )
        if entry is None:
            return False
        if (
            entry.cover_path
            and
            self.storage.exists(
                entry.cover_path
            )
            and
            not force
        ):
            return True

        details = (
            self.metadata_service
            .get_merged_details(
                entry.title
            )
        )
        if (
            details is None
            or
            not details.artwork_urls
        ):
            return False
        artwork_url = (
            self._select_best_cover(
                details.artwork_urls
            )
        )
        if artwork_url is None:
            return False
        contents, extension = (
            self._download_artwork_url(
                artwork_url
            )
        )
        relative_path = (
            f"covers/"
            f"{entry.id}"
            f"{extension}"
        )
        stored_path = (
            self.storage.save(
                relative_path,
                contents,
            )
        )
        if (
            entry.cover_path
            and
            entry.cover_path
            != stored_path
        ):
            self.storage.delete(
                entry.cover_path
            )
        entry.cover_path = (
            stored_path
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return True

    def auto_download_missing_artwork(self, db: Session,) -> dict:
        entries = (
            self.entry_repo
            .list_active(db)
        )
        downloaded = 0
        failed = 0
        for entry in entries:
            try:
                if (
                    not entry.cover_path
                ):
                    if self.auto_download_cover(
                        db,
                        entry.id,
                    ):
                        downloaded += 1
                    else:
                        failed += 1
            except Exception:
                failed += 1
        return {
            "downloaded": downloaded,
            "failed": failed,
        }

    def upload_artwork(
        self,
        db: Session,
        archive_entry_id: str,
        artwork_type: ArtworkType,
        file: UploadFile,
        caption: str | None = None,
    ) -> dict[str, str | None]:
        entry = self.entry_repo.get_active(db, archive_entry_id)
        if entry is None:
            raise ValueError("Archive entry not found")

        contents = self._read_file(file)
        relative_path = build_artwork_relative_path(archive_entry_id, artwork_type, file.filename)
        stored_path = self.storage.save(relative_path, contents)

        if artwork_type == ArtworkType.SCREENSHOT:
            screenshot = self.screenshot_repo.create(db, {
                "archive_entry_id": archive_entry_id,
                "file_path": stored_path,
                "caption": caption,
            })
            return {
                "archive_entry_id": archive_entry_id,
                "artwork_type": artwork_type.value,
                "file_path": stored_path,
                "screenshot_id": screenshot.id,
                "caption": screenshot.caption,
            }

        asset_field = f"{artwork_type.value}_path"
        existing_path = getattr(entry, asset_field, None)
        if existing_path:
            self.storage.delete(existing_path)

        setattr(entry, asset_field, stored_path)
        db.add(entry)
        db.commit()
        db.refresh(entry)

        return {
            "archive_entry_id": archive_entry_id,
            "artwork_type": artwork_type.value,
            "file_path": stored_path,
            "screenshot_id": None,
            "caption": None,
        }

    def replace_artwork(
        self,
        db: Session,
        archive_entry_id: str,
        artwork_type: ArtworkType,
        file: UploadFile,
        screenshot_id: str | None = None,
        caption: str | None = None,
    ) -> dict[str, str | None]:
        contents = self._read_file(file)

        if artwork_type == ArtworkType.SCREENSHOT:
            if not screenshot_id:
                raise ValueError("Screenshot ID is required for screenshot replacement")
            screenshot = self.screenshot_repo.get(db, screenshot_id)
            if screenshot is None:
                raise ValueError("Screenshot not found")
            self.storage.delete(screenshot.file_path)
            relative_path = build_artwork_relative_path(archive_entry_id, artwork_type, file.filename)
            screenshot.file_path = self.storage.save(relative_path, contents)
            if caption is not None:
                screenshot.caption = caption
            db.add(screenshot)
            db.commit()
            db.refresh(screenshot)
            return {
                "archive_entry_id": archive_entry_id,
                "artwork_type": artwork_type.value,
                "file_path": screenshot.file_path,
                "screenshot_id": screenshot.id,
                "caption": screenshot.caption,
            }

        entry = self.entry_repo.get_active(db, archive_entry_id)
        if entry is None:
            raise ValueError("Archive entry not found")
        asset_field = f"{artwork_type.value}_path"
        existing_path = getattr(entry, asset_field, None)
        if existing_path:
            self.storage.delete(existing_path)
        relative_path = build_artwork_relative_path(archive_entry_id, artwork_type, file.filename)
        setattr(entry, asset_field, self.storage.save(relative_path, contents))
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return {
            "archive_entry_id": archive_entry_id,
            "artwork_type": artwork_type.value,
            "file_path": getattr(entry, asset_field),
            "screenshot_id": None,
            "caption": None,
        }

    def delete_artwork(
        self,
        db: Session,
        artwork_id: str,
        artwork_type: ArtworkType | None = None,
    ) -> dict[str, str | None | bool]:
        if artwork_type is not None and artwork_type != ArtworkType.SCREENSHOT:
            entry = self.entry_repo.get_active(db, artwork_id)
            if entry is None:
                raise ValueError("Archive entry not found")
            asset_field = f"{artwork_type.value}_path"
            existing_path = getattr(entry, asset_field, None)
            if existing_path:
                self.storage.delete(existing_path)
                setattr(entry, asset_field, None)
                db.add(entry)
                db.commit()
                db.refresh(entry)
                return {
                    "archive_entry_id": artwork_id,
                    "artwork_type": artwork_type.value,
                    "screenshot_id": None,
                    "deleted": True,
                }
            raise ValueError("Artwork asset not found")

        screenshot = self.screenshot_repo.get(db, artwork_id)
        if screenshot is not None:
            self.storage.delete(screenshot.file_path)
            self.screenshot_repo.delete(db, screenshot)
            return {
                "archive_entry_id": screenshot.archive_entry_id,
                "artwork_type": ArtworkType.SCREENSHOT.value,
                "screenshot_id": screenshot.id,
                "deleted": True,
            }

        raise ValueError("Artwork not found")

    def list_missing_artwork(self, db: Session) -> list[dict[str, str | list[str]]]:
        entries = self.entry_repo.list_active(db)
        missing = []
        for entry in entries:
            missing_types: list[str] = []
            if not entry.cover_path:
                missing_types.append(ArtworkType.COVER.value)
            if not entry.banner_path:
                missing_types.append(ArtworkType.BANNER.value)
            if not entry.logo_path:
                missing_types.append(ArtworkType.LOGO.value)
            if len(entry.screenshots) == 0:
                missing_types.append(ArtworkType.SCREENSHOT.value)
            if missing_types:
                missing.append(
                    {
                        "archive_entry_id": entry.id,
                        "title": entry.title,
                        "missing_types": missing_types,
                    }
                )
        return missing

    def validate_all_artwork(self, db: Session,) -> list[dict]:
        entries = self.entry_repo.list_active(db)
        results = []
        for entry in entries:
            missing_types: list[str] = []
            corrupt_types: list[str] = []
            for artwork_type in (
                ArtworkType.COVER,
                ArtworkType.BANNER,
                ArtworkType.LOGO,
            ):
                asset_path = getattr(
                    entry,
                    f"{artwork_type.value}_path",
                    None,
                )
                if (
                    not asset_path
                    or
                    not self.storage.exists(
                        asset_path
                    )
                ):
                    missing_types.append(
                        artwork_type.value
                    )
                    continue
                absolute_path = (
                    self.storage.absolute_path(
                        asset_path
                    )
                )
                try:
                    with Image.open(
                        absolute_path
                    ) as image:
                        image.verify()
                except Exception:
                    corrupt_types.append(
                        artwork_type.value
                    )
            if len(entry.screenshots) == 0:
                missing_types.append(
                    ArtworkType.SCREENSHOT.value
                )
            if (
                missing_types
                or
                corrupt_types
            ):
                entry.verification_status = (
                    VerificationStatus.MISSING
                )
            else:
                entry.verification_status = (
                    VerificationStatus.VERIFIED
                )
            db.add(entry)
            results.append(
                {
                    "archive_id": entry.id,
                    "title": entry.title,
                    "verification_status":
                        entry.verification_status.value,
                    "missing_types":
                        missing_types,
                    "corrupt_types":
                        corrupt_types,
                }
            )
        db.commit()
        return results

    def validate_and_redownload_artwork(self, db: Session,) -> dict:
        validation = (
            self.validate_all_artwork(
                db
            )
        )
        repaired = 0
        failed = 0
        for item in validation:
            needs_repair = (
                "cover" in item["missing_types"]
                or
                "cover" in item["corrupt_types"]
            )
            if not needs_repair:
                continue
            try:
                if self.auto_download_cover(
                    db,
                    item["archive_id"],
                    force=True,
                ):
                    repaired += 1
                else:
                    failed += 1
            except Exception:
                failed += 1
        return {
            "repaired": repaired,
            "failed": failed,
        }
