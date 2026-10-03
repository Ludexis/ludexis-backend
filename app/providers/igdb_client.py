from datetime import datetime, timedelta, UTC

import httpx

from app.core.config import settings


class IGDBClient:
    def __init__(self) -> None:
        self.access_token: str | None = None
        self.client_id: str = ""
        self.expires_at: datetime | None = None

    def _token_expired(self) -> bool:
        if not self.access_token:
            return True

        if not self.expires_at:
            return True

        return datetime.now(UTC) >= self.expires_at

    def credentials(self) -> tuple[str, str]:
        # Environment variables win; otherwise the credentials saved in the admin settings are used.
        if settings.TWITCH_CLIENT_ID and settings.TWITCH_CLIENT_SECRET:
            return settings.TWITCH_CLIENT_ID, settings.TWITCH_CLIENT_SECRET
        from app.db.session import SessionLocal
        from app.services.settings import SettingsService

        with SessionLocal() as db:
            return SettingsService().igdb_credentials(db)

    def configured(self) -> bool:
        return all(self.credentials())

    def _refresh_token(self) -> None:
        self.client_id, client_secret = self.credentials()
        response = httpx.post(
            settings.IGDB_TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )

        response.raise_for_status()

        payload = response.json()

        self.access_token = payload["access_token"]

        self.expires_at = (
            datetime.now(UTC)
            + timedelta(seconds=payload["expires_in"] - 60)
        )

    def _ensure_token(self) -> None:
        if self._token_expired():
            self._refresh_token()

    def get_headers(self) -> dict[str, str]:
        self._ensure_token()

        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.access_token}",
        }

    def post(
        self,
        endpoint: str,
        query: str,
    ) -> list[dict]:
        self._ensure_token()

        response = httpx.post(
            f"{settings.IGDB_API_URL}/{endpoint}",
            headers=self.get_headers(),
            content=query,
            timeout=30,
        )

        response.raise_for_status()

        return response.json()