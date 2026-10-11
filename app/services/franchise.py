import uuid
from pathlib import Path

import requests
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.core.access import restricted_sources_allowed
from app.core.logging import get_logger
from app.models.franchise import Franchise
from app.providers.steamgriddb import SteamGridDBClient
from app.repositories.franchise import FranchiseRepository
from app.schemas.franchise import FranchiseCreate, FranchiseUpdate
from app.services.artwork import ArtworkService
from app.services.settings import SettingsService
from app.services.storage import StorageService
from app.utils.normalization import title_key

logger = get_logger(__name__)


class FranchiseService:
    def __init__(self) -> None:
        self.repo = FranchiseRepository()
        self.storage = StorageService()

    def _annotate(self, db: Session, franchises: list[Franchise], viewer) -> list[Franchise]:
        ids = [franchise.id for franchise in franchises]
        counts = self.repo.count_entries_for_ids(db, ids, viewer)
        # Without a chosen image a franchise shows one of its games' banners, as media servers do for collections.
        auto = self.repo.auto_images(db, [franchise.id for franchise in franchises if not franchise.banner_path], viewer)
        for franchise in franchises:
            franchise.entry_count = counts.get(franchise.id, 0)
            franchise.image_path = franchise.banner_path or auto.get(franchise.id)
        return franchises

    def list_items(self, db: Session, offset: int = 0, limit: int = 100, q: str | None = None, viewer=None) -> list[Franchise]:
        return self._annotate(db, self.repo.list_items(db, offset=offset, limit=limit, q=q, viewer=viewer), viewer)

    def count(self, db: Session, q: str | None = None, viewer=None) -> int:
        return self.repo.count(db, q=q, viewer=viewer)

    def get(self, db: Session, franchise_id: str, viewer=None) -> Franchise | None:
        franchise = self.repo.get(db, franchise_id)
        if franchise is not None:
            self._annotate(db, [franchise], viewer)
        return franchise

    def create(self, db: Session, data: FranchiseCreate) -> Franchise:
        franchise_data = data.model_dump(exclude={"child_ids"})
        return self.repo.create(db, franchise_data)

    def update(self, db: Session, franchise: Franchise, data: FranchiseUpdate) -> Franchise:
        update_data = data.model_dump(exclude={"child_ids"}, exclude_none=True)
        return self.repo.update(db, franchise, update_data)

    def delete(self, db: Session, franchise: Franchise) -> Franchise:
        self._drop_own_image(franchise)
        return self.repo.delete(db, franchise)

    def _drop_own_image(self, franchise: Franchise) -> None:
        # Only a file saved for this franchise is removed; an older hand-typed path may point at a game's art.
        path = (franchise.banner_path or "").replace("\\", "/")
        if path.startswith(f"franchises/{franchise.id}/"):
            self.storage.delete(path)

    def _game_art(self, db: Session, franchise: Franchise, viewer) -> tuple[list[str], list[str]]:
        """Banners and screenshots of the franchise's games this user can see."""
        entries = self.repo.visible_entries(db, franchise.id, viewer)
        banners = [entry.banner_path for entry in entries if entry.banner_path]
        return banners, [shot.file_path for entry in entries for shot in entry.screenshots]

    def _steamgriddb_candidates(self, db: Session, franchise: Franchise) -> list[str]:
        """Wide art SteamGridDB has for a game named exactly like the franchise, often its first title."""
        api_key = SettingsService().steamgriddb_key(db)
        if not api_key:
            return []
        client = SteamGridDBClient(api_key, all_ratings=restricted_sources_allowed(db))
        try:
            game = next((game for game in client.search(franchise.name) if title_key(game["name"]) == title_key(franchise.name)), None)
            return client.artwork(game["id"])["banner_urls"] if game else []
        except requests.RequestException:
            logger.warning("SteamGridDB lookup failed", extra={"franchise": franchise.name})
            return []

    def image_candidates(self, db: Session, franchise: Franchise, viewer) -> list[str]:
        """Images to choose from: the games' banners, SteamGridDB art, then the games' screenshots."""
        banners, screenshots = self._game_art(db, franchise, viewer)
        return list(dict.fromkeys(banners + self._steamgriddb_candidates(db, franchise) + screenshots))

    def set_image(self, db: Session, franchise: Franchise, source: str, viewer) -> None:
        # Only an offered image is copied, so the server never fetches an arbitrary URL or file.
        if source in sum(self._game_art(db, franchise, viewer), []):
            if not self.storage.exists(source):
                raise ValueError("That image is missing from storage")
            contents = self.storage.absolute_path(source).read_bytes()
            extension = Path(source).suffix.lower() or ".jpg"
        elif source in self._steamgriddb_candidates(db, franchise):
            try:
                contents, extension = ArtworkService()._download_artwork_url(source)
            except requests.RequestException as exc:
                raise ValueError("The image could not be downloaded") from exc
        else:
            raise ValueError("That image is not offered for this franchise")
        self._save_image(db, franchise, contents, extension)

    def upload_image(self, db: Session, franchise: Franchise, file: UploadFile) -> None:
        contents = ArtworkService()._read_file(file)
        self._save_image(db, franchise, contents, Path(file.filename or "").suffix.lower() or ".png")

    def clear_image(self, db: Session, franchise: Franchise) -> None:
        self._drop_own_image(franchise)
        franchise.banner_path = None
        db.commit()

    def _save_image(self, db: Session, franchise: Franchise, contents: bytes, extension: str) -> None:
        # A copy, so replacing a game's banner later never breaks the franchise card.
        self._drop_own_image(franchise)
        franchise.banner_path = self.storage.save(f"franchises/{franchise.id}/{uuid.uuid4().hex}{extension}", contents)
        db.commit()
