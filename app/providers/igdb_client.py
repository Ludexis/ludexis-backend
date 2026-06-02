from datetime import datetime, timedelta, UTC

import httpx

from app.core.config import settings


class IGDBClient:
    def __init__(self) -> None:
        self.access_token: str | None = None
        self.expires_at: datetime | None = None

    def _token_expired(self) -> bool:
        if not self.access_token:
            return True

        if not self.expires_at:
            return True

        return datetime.now(UTC) >= self.expires_at

    def _refresh_token(self) -> None:
        response = httpx.post(
            settings.IGDB_TOKEN_URL,
            params={
                "client_id": settings.TWITCH_CLIENT_ID,
                "client_secret": settings.TWITCH_CLIENT_SECRET,
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
            "Client-ID": settings.TWITCH_CLIENT_ID,
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