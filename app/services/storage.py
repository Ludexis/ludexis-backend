from pathlib import Path

from app.core.config import settings


class StorageService:
    def __init__(self) -> None:
        self.base_dir = Path(settings.ARTWORK_STORAGE_PATH).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save(self, relative_path: str, contents: bytes) -> str:
        destination = self.base_dir.joinpath(relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(contents)
        return str(relative_path)

    def delete(self, relative_path: str) -> None:
        if not relative_path:
            return
        path = self.base_dir.joinpath(relative_path)
        if path.exists():
            path.unlink()

    def exists(self, relative_path: str) -> bool:
        if not relative_path:
            return False
        path = self.base_dir.joinpath(relative_path)
        return path.exists()

    def absolute_path(self, relative_path: str) -> Path:
        return self.base_dir.joinpath(relative_path)
