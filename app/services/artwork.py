from pathlib import Path
import time
import requests
from fastapi import UploadFile
from sqlalchemy.orm import Session, object_session
from PIL import Image
import hashlib

from app.core.config import settings
from app.models.archive_entry import ArchiveEntry
from app.models.screenshot import Screenshot
from app.repositories.archive_entry import ArchiveEntryRepository
from app.repositories.screenshot import ScreenshotRepository
from app.services.storage import StorageService
from app.schemas.metadata import MetadataDetails
from app.services.metadata import MetadataService
from app.core.access import restricted_sources_allowed
from app.services.settings import SettingsService
from app.providers.steamgriddb import SteamGridDBClient
from app.utils.cover_fit import content_ratio, fit_cover
from app.utils.normalization import title_key
from app.utils.artwork import ArtworkType, build_artwork_relative_path, is_allowed_artwork_mime_type
from app.utils.enums import MetadataStatus
from app.models.screenshot import Screenshot

from app.core.logging import get_logger
from app.core.metrics import (
    artwork_downloads_total,
    artwork_validation_failures_total,
    artwork_deduplications_total,
    artwork_auto_download_runs_total,
)

logger = get_logger(__name__)

SHAPE_BONUS = 1000
# Most years a SteamGridDB game may differ from the matched record's release date.
MAX_YEAR_GAP = 2
# Screenshots scored as a banner fallback; each one is downloaded to be measured.
SCREENSHOT_BANNER_CANDIDATES = 4
# Unreferenced files younger than this may belong to a download still being saved.
ORPHAN_MIN_AGE_SECONDS = 3600


class ArtworkService:
    def __init__(self, metadata_service: MetadataService | None = None) -> None:
        self.entry_repo = ArchiveEntryRepository()
        self.screenshot_repo = ScreenshotRepository()
        self.storage = StorageService()
        self.metadata_service = metadata_service or MetadataService()

    def _entry_details(self, entry: ArchiveEntry) -> MetadataDetails | None:
        # Prefer the stored provider match; fall back to a title search only for entries without one.
        db = object_session(entry)
        details = self.metadata_service.get_merged_details(
            entry.title,
            entry.metadata_source if entry.metadata_source_code else None,
            entry.metadata_source_code,
            db,
        )
        if details is not None and db is not None:
            self._add_steamgriddb_art(db, details)
        return details

    def _add_steamgriddb_art(self, db: Session, details: MetadataDetails) -> None:
        # Community art is offered after the sources' own, so official art wins a tie; it matters most
        # where no source has a portrait cover or a wide banner.
        settings_service = SettingsService()
        api_key = settings_service.steamgriddb_key(db)
        if not api_key:
            return
        client = SteamGridDBClient(api_key, all_ratings=restricted_sources_allowed(db))
        year = details.release_date.year if details.release_date else None
        try:
            same_name = [game for game in client.search(details.title) if title_key(game["name"]) == title_key(details.title)]
            # Among same-named games the closest release year wins. Early-access games are dated by their
            # launch on one site and their full release on another, hence the two-year allowance.
            gap = lambda game: abs(year - game["year"]) if year and game["year"] else 0
            game = min(same_name, key=gap, default=None)
            if game is None or gap(game) > MAX_YEAR_GAP:
                return
            for field, urls in client.artwork(game["id"]).items():
                setattr(details, field, getattr(details, field) + [url for url in urls if url not in getattr(details, field)])
        except requests.RequestException:
            logger.warning("SteamGridDB lookup failed", extra={"title": details.title})

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

    def _select_best_url(self, urls: list[str], shape: str | None = None, shape_only: list[str] | tuple = ()) -> str | None:
        # shape "portrait" (covers) or "landscape" (banners) outweighs size and source, so a big
        # landscape image never wins a cover slot over a smaller portrait one. URLs in shape_only
        # are dropped unless they have the shape.
        best_url = None
        best_score = -1
        for url in dict.fromkeys(urls):
            score = self._score_artwork_candidate(url)
            try:
                contents, _ = self._download_artwork_url(url)
                image_score = self._score_image(contents, shape)
            except Exception:
                image_score = 0
            if url in shape_only and image_score < SHAPE_BONUS:
                continue
            score += image_score
            if score > best_score:
                best_score = score
                best_url = url
        return best_url

    def auto_download_cover(self, db: Session, archive_entry_id: str, force: bool = False, details: MetadataDetails | None = None,) -> bool:
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

        details = details or self._entry_details(entry)
        if (
            details is None
            or
            not details.cover_urls
        ):
            return False

        artwork_url = (
            self._select_best_url(details.cover_urls, "portrait")
        )
        if artwork_url is None:
            return False
        contents, extension = (
            self._download_artwork_url(
                artwork_url
            )
        )
        # With no portrait art on offer, the best image is cropped to the card; a new name keeps
        # browsers from showing the old file they cached.
        fitted = fit_cover(contents)
        relative_path = (
            f"covers/"
            f"{entry.id}"
            f"{'-card' if fitted else ''}"
            f"{extension}"
        )
        contents = fitted or contents
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
        artwork_downloads_total.inc()
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

    def auto_download_banner(self, db: Session, archive_entry_id: str, force: bool = False, details: MetadataDetails | None = None,) -> bool:
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
        details = details or self._entry_details(entry)
        if details is None:
            return False
        # A landscape "cover" (common on VNDB) is usually the game's key art and makes a better banner
        # than a small store header, so cover candidates compete for the banner too.
        artwork_url = self._select_best_url(details.banner_urls + details.cover_urls, "landscape", shape_only=details.cover_urls)
        # Without key art, a screenshot of the matched game still beats an empty or stale backdrop.
        artwork_url = artwork_url or self._select_best_url(details.artwork_urls[:SCREENSHOT_BANNER_CANDIDATES], "landscape")
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
        artwork_downloads_total.inc()
        logger.info(
            "Banner artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "path": stored_path,
            },
        )
        return True

    def auto_download_logo(self, db: Session, archive_entry_id: str, force: bool = False, details: MetadataDetails | None = None,) -> bool:
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
        details = details or self._entry_details(entry)
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
        artwork_downloads_total.inc()
        logger.info(
            "Logo artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "path": stored_path,
            },
        )
        return True

    def auto_download_screenshots(self, db: Session, archive_entry_id: str, force: bool = False, details: MetadataDetails | None = None,) -> bool:
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
        details = details or self._entry_details(entry)
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
        artwork_downloads_total.inc()
        logger.info(
            "Screenshot artwork downloaded",
            extra={
                "archive_id": entry.id,
                "title": entry.title,
                "screenshots_imported": imported,
            },
        )
        return True

    def fill_missing_artwork(self, db: Session, entry: ArchiveEntry, repair: list[str] | tuple[str, ...] = (), clear_unoffered: bool = False) -> int:
        # Provider details are fetched once and shared by every asset type that needs downloading.
        wanted = [
            kind for kind in ("cover", "banner", "logo")
            if kind in repair or not getattr(entry, f"{kind}_path")
        ]
        if "screenshots" in repair or len(entry.screenshots) == 0:
            wanted.append("screenshots")
        if not wanted:
            return 0
        details = self._entry_details(entry)
        if details is None:
            return 0
        downloaders = {
            "cover": self.auto_download_cover,
            "banner": self.auto_download_banner,
            "logo": self.auto_download_logo,
            "screenshots": self.auto_download_screenshots,
        }
        downloaded = 0
        for kind in wanted:
            try:
                if downloaders[kind](db, entry.id, force=True, details=details):
                    downloaded += 1
                elif clear_unoffered and kind != "screenshots" and getattr(entry, f"{kind}_path"):
                    # The new match has no image for this slot; the old one belongs to whatever was matched before.
                    self.storage.delete(getattr(entry, f"{kind}_path"))
                    setattr(entry, f"{kind}_path", None)
                    db.commit()
            except Exception:
                db.rollback()
                artwork_validation_failures_total.inc()
                logger.warning(
                    "Artwork download failed",
                    extra={
                        "archive_id": entry.id,
                        "title": entry.title,
                        "artwork_type": kind,
                    },
                )
        return downloaded

    def replace_entries_artwork(self, db: Session, entry_ids: list[str], on_progress=None) -> dict:
        downloaded = 0
        entries = [entry for entry in (self.entry_repo.get_active(db, entry_id) for entry_id in entry_ids) if entry]
        for index, entry in enumerate(entries, start=1):
            downloaded += self.fill_missing_artwork(db, entry, repair=("cover", "banner", "logo", "screenshots"), clear_unoffered=True)
            if on_progress:
                on_progress(index, len(entries))
        return {"entries": len(entries), "downloaded": downloaded}

    def auto_download_missing_artwork(self, db: Session,) -> dict:
        artwork_auto_download_runs_total.inc()
        downloaded = 0
        failed = 0
        for entry in self.entry_repo.list_active(db, limit=None):
            try:
                downloaded += self.fill_missing_artwork(db, entry)
            except Exception:
                db.rollback()
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
            if screenshot.archive_entry_id != archive_entry_id:
                raise ValueError("Screenshot does not belong to the given archive entry")
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

    def artwork_candidates(self, db: Session, archive_entry_id: str, artwork_type: ArtworkType) -> list[str]:
        """Images the entry's matched sources offer for one slot, for the user to choose from."""
        entry = self.entry_repo.get_active(db, archive_entry_id)
        if entry is None:
            raise ValueError("Archive entry not found")
        details = self._entry_details(entry)
        if details is None:
            return []
        candidates = {
            ArtworkType.COVER: details.cover_urls,
            # Wide key art often sits among covers (VNDB) or screenshots, so a banner may come from either.
            ArtworkType.BANNER: details.banner_urls + details.cover_urls + details.artwork_urls,
            ArtworkType.LOGO: details.logo_urls,
        }.get(artwork_type, [])
        return list(dict.fromkeys(candidates))

    def set_artwork_from_url(self, db: Session, archive_entry_id: str, artwork_type: ArtworkType, url: str) -> dict[str, str | None]:
        # Only an offered candidate is fetched, so the server never downloads an arbitrary URL.
        if artwork_type == ArtworkType.SCREENSHOT or url not in self.artwork_candidates(db, archive_entry_id, artwork_type):
            raise ValueError("That image is not offered for this game")
        entry = self.entry_repo.get_active(db, archive_entry_id)
        try:
            contents, extension = self._download_artwork_url(url)
        except requests.RequestException as exc:
            raise ValueError("The image could not be downloaded") from exc
        fitted = fit_cover(contents) if artwork_type == ArtworkType.COVER else None
        contents = fitted or contents
        asset_field = f"{artwork_type.value}_path"
        existing_path = getattr(entry, asset_field, None)
        stored_path = self.storage.save(
            build_artwork_relative_path(entry.id, artwork_type, f"art{'-card' if fitted else ''}{extension}"), contents
        )
        if existing_path and existing_path != stored_path:
            self.storage.delete(existing_path)
        setattr(entry, asset_field, stored_path)
        db.add(entry)
        db.commit()
        return {"archive_entry_id": entry.id, "artwork_type": artwork_type.value, "file_path": stored_path, "screenshot_id": None, "caption": None}

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
        entries = self.entry_repo.list_active(db, limit=None)
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
        # Reports artwork problems only; verification_status belongs to the archive file and is set by integrity checks.
        entries = self.entry_repo.list_active(db, limit=None)
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
            results.append(
                {
                    "archive_id": entry.id,
                    "title": entry.title,
                    "complete": not (missing_types or corrupt_types),
                    "missing_types":
                        missing_types,
                    "corrupt_types":
                        corrupt_types,
                }
            )
        return results

    def validate_and_redownload_artwork(self, db: Session,) -> dict:
        validation = self.validate_all_artwork(db)
        repaired = 0
        failed = 0
        for item in validation:
            broken = item["missing_types"] + item["corrupt_types"]
            if not broken:
                continue
            entry = self.entry_repo.get_active(db, item["archive_id"])
            # Only entries with a provider match have a trustworthy artwork source.
            if (
                entry is None
                or not entry.metadata_source_code
                or entry.metadata_status == MetadataStatus.UNMATCHED
            ):
                continue
            try:
                if self.fill_missing_artwork(db, entry, repair=broken):
                    repaired += 1
            except Exception:
                db.rollback()
                failed += 1
        return {
            "checked": len(validation),
            "incomplete": sum(1 for item in validation if not item["complete"]),
            "repaired": repaired,
            "failed": failed,
            "covers_fitted": self.fit_stored_covers(db),
            "unused_removed": self.garbage_collect_artwork(db)["deleted"],
        }

    def fit_stored_covers(self, db: Session) -> int:
        """Crops saved covers that do not fit the library card; returns how many changed."""
        fitted_count = 0
        for entry in self.entry_repo.list_active(db, limit=None):
            if not entry.cover_path or not self.storage.exists(entry.cover_path):
                continue
            fitted = fit_cover(self.storage.absolute_path(entry.cover_path).read_bytes())
            if fitted is None:
                continue
            old_path = entry.cover_path
            stem, dot, extension = old_path.rpartition(".")
            entry.cover_path = self.storage.save(f"{stem}-card{dot}{extension}", fitted)
            if entry.cover_path != old_path:
                self.storage.delete(old_path)
            db.add(entry)
            db.commit()
            fitted_count += 1
        return fitted_count

    def _score_image(self, contents: bytes, shape: str | None = None) -> int:
        score = 0
        try:
            from io import BytesIO
            with Image.open(BytesIO(contents)) as image:
                width, height = image.size
                score += (width * height) // 10000
                if width >= 1000:
                    score += 50
                if height >= 500:
                    score += 50
                # Judged on the picture inside any padding bars: landscape art padded to portrait is not a cover.
                if shape == "portrait" and (content_ratio(contents) or width / height) < 1:
                    score += SHAPE_BONUS
                if shape == "landscape" and width >= 1.6 * height:
                    score += SHAPE_BONUS
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
        artwork_deduplications_total.inc()
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
    
    def garbage_collect_artwork(self, db: Session) -> dict:
        """Delete stored images no entry or screenshot points at: art left by removed entries or interrupted saves."""
        referenced = {
            path.replace("\\", "/")
            for row in db.query(ArchiveEntry.cover_path, ArchiveEntry.banner_path, ArchiveEntry.logo_path).all()
            for path in row
            if path
        }
        referenced.update(path.replace("\\", "/") for (path,) in db.query(Screenshot.file_path).all() if path)
        cutoff = time.time() - ORPHAN_MIN_AGE_SECONDS
        deleted = kept = 0
        for file_path in self.storage.base_dir.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.relative_to(self.storage.base_dir).as_posix() in referenced or file_path.stat().st_mtime > cutoff:
                kept += 1
                continue
            file_path.unlink()
            deleted += 1
        if deleted:
            logger.info("Unused artwork removed", extra={"deleted": deleted, "kept": kept})
        return {"deleted": deleted, "kept": kept}

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