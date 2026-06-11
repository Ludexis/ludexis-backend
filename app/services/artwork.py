from pathlib import Path
import requests
from fastapi import UploadFile
from sqlalchemy.orm import Session
from PIL import Image
import hashlib

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.models.screenshot import Screenshot
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.screenshot import ScreenshotRepository
from app.services.storage import StorageService
from app.services.metadata import MetadataService
from app.utils.artwork import ArtworkType, build_artwork_relative_path, is_allowed_artwork_mime_type
from app.utils.enums import VerificationStatus
from app.models.screenshot import Screenshot

from app.core.logging import get_logger

logger = get_logger(__name__)


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
    
    def _score_artwork_candidate(self, url: str,) -> int:
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

    def _select_best_url(self, urls: list[str],) -> str | None:
        if not urls:
            return None
        best_url = None
        best_score = -1
        for url in urls:
            score = (
                self._score_artwork_candidate(
                    url
                )
            )
            try:
                contents, _ = (
                    self._download_artwork_url(
                        url
                    )
                )
                score += (
                    self._score_image(
                        contents
                    )
                )
            except Exception:
                pass
            if score > best_score:
                best_score = score
                best_url = url
        return best_url

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
            not details.cover_urls
        ):
            return False

        artwork_url = (
            self._select_best_url(
                details.cover_urls
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
        logger.info(
            "Cover artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "path": stored_path,
            },
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        return True

    def auto_download_banner(self, db: Session, archive_entry_id: str, force: bool = False,) -> bool:
        entry = self.entry_repo.get_active(
            db,
            archive_entry_id,
        )
        if entry is None:
            return False
        if (
            entry.banner_path
            and
            self.storage.exists(
                entry.banner_path
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
            not details.banner_urls
        ):
            return False
        artwork_url = (
            self._select_best_url(
                details.banner_urls
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
            f"banners/"
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
            entry.banner_path
            and
            entry.banner_path != stored_path
        ):
            self.storage.delete(
                entry.banner_path
            )
        entry.banner_path = stored_path
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(
            "Banner artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "path": stored_path,
            },
        )
        return True

    def auto_download_logo(self, db: Session, archive_entry_id: str, force: bool = False,) -> bool:
        entry = self.entry_repo.get_active(
            db,
            archive_entry_id,
        )
        if entry is None:
            return False
        if (
            entry.logo_path
            and
            self.storage.exists(
                entry.logo_path
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
            not details.logo_urls
        ):
            return False
        artwork_url = (
            self._select_best_url(
                details.logo_urls
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
            f"logos/"
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
            entry.logo_path
            and
            entry.logo_path != stored_path
        ):
            self.storage.delete(
                entry.logo_path
            )
        entry.logo_path = stored_path
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(
            "Logo artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "path": stored_path,
            },
        )
        return True

    def auto_download_screenshots(self, db: Session, archive_entry_id: str, force: bool = False,) -> bool:
        entry = self.entry_repo.get_active(
            db,
            archive_entry_id,
        )
        if entry is None:
            return False
        if (
            len(entry.screenshots) > 0
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
        imported = self._download_screenshots(
            db,
            entry,
            details.artwork_urls,
        )
        db.add(entry)
        db.commit()
        db.refresh(entry)
        logger.info(
            "Screenshot artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "screenshots_imported": imported,
            },
        )
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

                if not entry.cover_path:
                    if self.auto_download_cover(
                        db,
                        entry.id,
                    ):
                        downloaded += 1

                if not entry.banner_path:
                    if self.auto_download_banner(
                        db,
                        entry.id,
                    ):
                        downloaded += 1

                if not entry.logo_path:
                    if self.auto_download_logo(
                        db,
                        entry.id,
                    ):
                        downloaded += 1

                if len(entry.screenshots) == 0:
                    if self.auto_download_screenshots(
                        db,
                        entry.id,
                    ):
                        downloaded += 1

            except Exception:
                failed += 1
                logger.warning(
                    "Artwork download failed",
                    extra={
                        "archive_id": entry.id,
                        "title": entry.title,
                    },
                )
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
                    logger.warning(
                        "Artwork validation failed",
                        extra={
                            "archive_id": entry.id,
                            "title": entry.title,
                            "artwork_type": artwork_type.value,
                        },
                    )

                    corrupt_types.append(
                        artwork_type.value
                    )
            if (
                hasattr(
                    entry,
                    "screenshots",
                )
                and
                len(
                    entry.screenshots
                ) == 0
            ):
                pass
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

                repaired_this_entry = False

                if (
                    "cover" in item["missing_types"]
                    or
                    "cover" in item["corrupt_types"]
                ):
                    repaired_this_entry |= (
                        self.auto_download_cover(
                            db,
                            item["archive_id"],
                            force=True,
                        )
                    )

                if (
                    "banner" in item["missing_types"]
                    or
                    "banner" in item["corrupt_types"]
                ):
                    repaired_this_entry |= (
                        self.auto_download_banner(
                            db,
                            item["archive_id"],
                            force=True,
                        )
                    )

                if (
                    "logo" in item["missing_types"]
                    or
                    "logo" in item["corrupt_types"]
                ):
                    repaired_this_entry |= (
                        self.auto_download_logo(
                            db,
                            item["archive_id"],
                            force=True,
                        )
                    )

                if repaired_this_entry:
                    repaired += 1

            except Exception:
                failed += 1
        return {
            "repaired": repaired,
            "failed": failed,
        }
    
    def _score_image(self, contents: bytes, ) -> int:
        score = 0
        try:
            from io import BytesIO
            with Image.open(
                BytesIO(contents)
            ) as image:
                width, height = (
                    image.size
                )
                score += (
                    width * height
                ) // 10000
                if width >= 1000:
                    score += 50
                if height >= 500:
                    score += 50
        except Exception:
            return 0
        return score

    def _file_sha256(self, relative_path: str,) -> str | None:
        if not relative_path:
            return None
        if not self.storage.exists(
            relative_path
        ):
            return None
        path = (
            self.storage.absolute_path(
                relative_path
            )
        )
        digest = hashlib.sha256()
        with open(
            path,
            "rb",
        ) as handle:
            while chunk := handle.read(
                8192
            ):
                digest.update(
                    chunk
                )
        return digest.hexdigest()
    
    def find_duplicate_artwork(self, db,) -> list[dict]:
        hashes = {}
        archives = (
            db.query(
                ArchiveEntry
            )
            .all()
        )
        for archive in archives:
            for asset_type, asset_path in (
                (
                    "cover",
                    archive.cover_path,
                ),
                (
                    "banner",
                    archive.banner_path,
                ),
                (
                    "logo",
                    archive.logo_path,
                ),
            ):
                
                if not asset_path:
                    continue

                if asset_path.startswith(
                    "dedup/"
                ):
                    continue

                file_hash = (
                    self._file_sha256(
                        asset_path
                    )
                )
                if not file_hash:
                    continue
                hashes.setdefault(
                    (
                        file_hash,
                        asset_type,
                    ),
                    [],
                ).append(
                    {
                        "archive_id": archive.id,
                        "title": archive.title,
                        "type": asset_type,
                        "path": asset_path,
                    }
                )
        duplicates = []
        for (
            file_hash,
            asset_type,
        ), assets in (
            hashes.items()
        ):
            if len(
                assets
            ) <= 1:
                continue
            archive_ids = {
                asset["archive_id"]
                for asset in assets
            }
            if len(
                archive_ids
            ) < 2:
                continue
            duplicates.append(
                {
                    "hash": file_hash,
                    "count": len(
                        assets
                    ),
                    "assets": assets,
                }
            )
        return duplicates

    def _canonical_artwork_path(self, file_hash: str, asset_type: str,) -> str:
        return (
            f"dedup/"
            f"{asset_type}/"
            f"{file_hash}.jpg"
        )
    
    def deduplicate_artwork(self, db,) -> dict:
        duplicates = (
            self.find_duplicate_artwork(
                db
            )
        )
        deduplicated = 0
        for group in duplicates:
            file_hash = (
                group["hash"]
            )
            asset_type = (
                group["assets"][0]["type"]
            )
            canonical_path = (
                self._canonical_artwork_path(
                    file_hash,
                    asset_type,
                )
            )
            first_asset = (
                group["assets"][0]
            )
            source_path = (
                first_asset["path"]
            )
            if not self.storage.exists(
                canonical_path
            ):
                contents = (
                    self.storage
                    .absolute_path(
                        source_path
                    )
                    .read_bytes()
                )
                self.storage.save(
                    canonical_path,
                    contents,
                )
            for asset in (
                group["assets"]
            ):
                archive = (
                    db.query(
                        ArchiveEntry
                    )
                    .filter(
                        ArchiveEntry.id
                        == asset[
                            "archive_id"
                        ]
                    )
                    .first()
                )
                if (
                    asset["type"]
                    == "cover"
                ):
                    archive.cover_path = (
                        canonical_path
                    )
                elif (
                    asset["type"]
                    == "banner"
                ):
                    archive.banner_path = (
                        canonical_path
                    )
                elif (
                    asset["type"]
                    == "logo"
                ):
                    archive.logo_path = (
                        canonical_path
                    )
                deduplicated += 1
            db.add(
                archive
            )
        db.commit()
        logger.info(
            "Artwork deduplication completed",
            extra={
                "duplicates_found": len(duplicates),
                "deduplicated": deduplicated,
            },
        )
        return {
            "deduplicated":
            deduplicated,
        }
    
    def garbage_collect_artwork(self, db,) -> dict:
        referenced = set()
        archives = (
            db.query(
                ArchiveEntry
            )
            .all()
        )
        for archive in archives:
            for asset_path in (
                archive.cover_path,
                archive.banner_path,
                archive.logo_path,
            ):
                if asset_path:
                    referenced.add(
                        asset_path
                    )
        deleted = 0
        kept = 0
        covers_dir = (
            self.storage.absolute_path(
                "covers"
            )
        )
        banners_dir = (
            self.storage.absolute_path(
                "banners"
            )
        )
        logos_dir = (
            self.storage.absolute_path(
                "logos"
            )
        )
        for directory in (
            covers_dir,
            banners_dir,
            logos_dir,
        ):
            if not directory.exists():
                continue
            for file_path in directory.rglob(
                "*"
            ):
                if not file_path.is_file():
                    continue
                relative_path = str(
                    file_path.relative_to(
                        self.storage.base_dir
                    )
                ).replace(
                    "\\",
                    "/",
                )
                if (
                    relative_path
                    in referenced
                ):
                    kept += 1
                    continue
                file_path.unlink()
                deleted += 1
        return {
            "deleted": deleted,
            "kept": kept,
        }
    
    def _download_screenshots(self, db, archive, screenshot_urls: list[str],) -> int:
        imported = 0
        for screenshot in list(
            archive.screenshots
        ):
            self.storage.delete(
                screenshot.file_path
            )
            db.delete(
                screenshot
            )
        for index, url in enumerate(
            screenshot_urls,
            start=1,
        ):
            try:
                contents, extension = (
                    self._download_artwork_url(
                        url
                    )
                )
                relative_path = (
                    f"screenshots/"
                    f"{archive.id}_"
                    f"{index}"
                    f"{extension}"
                )
                self.storage.save(
                    relative_path,
                    contents,
                )
                screenshot = Screenshot(
                    archive_entry_id=archive.id,
                    file_path=relative_path,
                )
                db.add(
                    screenshot
                )
                imported += 1
            except Exception:
                continue
        return imported