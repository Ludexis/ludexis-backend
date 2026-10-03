from sqlalchemy.orm import Session

from app.core.config import settings as env
from app.models.system import SystemSetting

DEFAULTS = {
    "server_name": "Ludexis",
    # Providers auto-matching tries, in order; a provider left out is disabled.
    "provider_order": ["VNDB", "IGDB", "Steam"],
    "igdb_client_id": "",
    "igdb_client_secret": "",
}
MATCH_PROVIDERS = ["VNDB", "IGDB", "Steam"]


class SettingsService:
    def get(self, db: Session, key: str):
        row = db.get(SystemSetting, key)
        return row.value if row is not None else DEFAULTS[key]

    def set(self, db: Session, key: str, value) -> None:
        row = db.get(SystemSetting, key)
        if row is None:
            db.add(SystemSetting(key=key, value=value))
        else:
            row.value = value
        db.commit()

    def igdb_credentials(self, db: Session) -> tuple[str, str]:
        # Environment variables win, so a compose file can pin them.
        if env.TWITCH_CLIENT_ID and env.TWITCH_CLIENT_SECRET:
            return env.TWITCH_CLIENT_ID, env.TWITCH_CLIENT_SECRET
        return self.get(db, "igdb_client_id"), self.get(db, "igdb_client_secret")

    def public(self, db: Session) -> dict:
        client_id, client_secret = self.igdb_credentials(db)
        return {
            "server_name": self.get(db, "server_name"),
            "provider_order": self.get(db, "provider_order"),
            "available_providers": MATCH_PROVIDERS,
            "igdb_client_id": client_id,
            "igdb_configured": bool(client_id and client_secret),
            "igdb_from_env": bool(env.TWITCH_CLIENT_ID and env.TWITCH_CLIENT_SECRET),
        }
