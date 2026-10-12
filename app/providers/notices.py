"""Short-lived warnings a metadata provider raises about itself, such as an expired sign-in or a reached rate limit.

Kept in Redis so a notice raised in a worker shows up in the app as well.
"""
from datetime import UTC, datetime, timedelta

from redis import Redis, RedisError

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_client: Redis | None = None


def _redis() -> Redis:
    global _client
    if _client is None:
        _client = Redis.from_url(str(settings.REDIS_URL), socket_timeout=1, decode_responses=True)
    return _client


def _key(provider: str) -> str:
    return f"provider-notice:{provider}"


def set_notice(provider: str, message: str, seconds: int) -> None:
    """Shows message for this provider until it expires or clear_notice is called."""
    try:
        _redis().set(_key(provider), message, ex=seconds)
    except RedisError:
        logger.warning("Provider notice unavailable", extra={"provider": provider})


def clear_notice(provider: str) -> None:
    try:
        _redis().delete(_key(provider))
    except RedisError:
        logger.warning("Provider notice unavailable", extra={"provider": provider})


def get_notices(providers: list[str]) -> list[dict]:
    """The current notices of these providers, each with the time it lapses."""
    notices = []
    try:
        for provider in providers:
            message = _redis().get(_key(provider))
            if message:
                seconds = _redis().ttl(_key(provider))
                expires_at = datetime.now(UTC) + timedelta(seconds=seconds) if seconds > 0 else None
                notices.append({"provider": provider, "message": message, "expires_at": expires_at})
    except RedisError:
        logger.warning("Provider notices unavailable")
    return notices
