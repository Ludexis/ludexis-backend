from redis import Redis, RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

MAX_FAILURES = 5
WINDOW_SECONDS = 15 * 60


class LoginRateLimiter:
    """Blocks a username from one address after repeated failed logins, for a fixed window."""

    def __init__(self, client: Redis | None = None) -> None:
        self._client = client

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis.from_url(str(settings.REDIS_URL), socket_timeout=1)
        return self._client

    @staticmethod
    def _key(username: str, address: str) -> str:
        return f"login-failures:{username.strip().lower()}:{address}"

    def retry_after(self, username: str, address: str) -> int | None:
        """Seconds until the next attempt is allowed, or None when not blocked."""
        try:
            key = self._key(username, address)
            if int(self.client.get(key) or 0) < MAX_FAILURES:
                return None
            return max(int(self.client.ttl(key)), 1)
        except RedisError:
            # Redis down: logins keep working rather than locking everyone out.
            logger.warning("Login rate limit unavailable")
            return None

    def record_failure(self, username: str, address: str) -> None:
        try:
            key = self._key(username, address)
            if self.client.incr(key) == 1:
                self.client.expire(key, WINDOW_SECONDS)
        except RedisError:
            logger.warning("Login rate limit unavailable")

    def reset(self, username: str, address: str) -> None:
        try:
            self.client.delete(self._key(username, address))
        except RedisError:
            pass
