"""
Global OpenRouter call-rate limiter.

OpenRouter free tier allows 50 requests/day, resetting at UTC midnight.
This module tracks a shared in-process counter across all users.

IMPORTANT: For multi-instance deployments (multiple processes or replicas),
move this counter to Redis (INCR + EXPIREAT) or a dedicated DB row so all
instances share the same counter.  The current in-process implementation is
safe only for single-process deployments (e.g., uvicorn with --workers 1).
"""

import asyncio
import logging
from datetime import date, datetime, timezone

logger = logging.getLogger(__name__)

# ── Module-level state ────────────────────────────────────────────────────────

_calls_today: int = 0
_reset_date: date = datetime.now(timezone.utc).date()
_lock: asyncio.Lock = asyncio.Lock()

_DAILY_LIMIT: int = 50
_WARNING_THRESHOLD: int = 45  # warn when calls_today >= this value


# ── Custom exception ──────────────────────────────────────────────────────────


class RateLimitError(Exception):
    """
    Raised when the OpenRouter daily call limit is reached.

    Attributes:
        message:   User-facing Korean error string (safe for API response).
        remaining: How many calls remain (always 0 when this is raised).
    """

    def __init__(self, message: str, remaining: int = 0, resets_at_utc: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.remaining = remaining
        self.resets_at_utc = resets_at_utc


# ── Internal helpers ──────────────────────────────────────────────────────────


def _reset_if_new_day() -> None:
    """Reset counter if UTC date has rolled over since last call. NOT thread-safe — caller holds _lock."""
    global _calls_today, _reset_date
    today = datetime.now(timezone.utc).date()
    if today != _reset_date:
        _calls_today = 0
        _reset_date = today


def _next_midnight_utc() -> str:
    """Return the ISO-8601 timestamp of the next UTC midnight."""
    from datetime import timedelta

    today = datetime.now(timezone.utc).date()
    tomorrow = today + timedelta(days=1)
    return datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=timezone.utc).isoformat()


# ── Public API ────────────────────────────────────────────────────────────────


async def consume(n: int = 1) -> None:
    """
    Record n OpenRouter API call(s) against today's quota.

    Must be called BEFORE each actual API call to prevent over-consumption.
    Raises RateLimitError (HTTP 429) if adding n calls would meet or exceed the limit.

    Args:
        n: Number of calls to consume (default 1).

    Raises:
        RateLimitError: when the daily limit has been reached.
    """
    async with _lock:
        global _calls_today
        _reset_if_new_day()

        remaining = _DAILY_LIMIT - _calls_today
        if remaining <= 0:
            raise RateLimitError(
                message=(
                    "OpenRouter 일일 요청 한도(50회)를 초과했습니다. "
                    "내일 UTC 자정에 초기화됩니다."
                ),
                remaining=0,
                resets_at_utc=_next_midnight_utc(),
            )

        _calls_today += n

        if _calls_today >= _WARNING_THRESHOLD:
            calls_left = _DAILY_LIMIT - _calls_today
            logger.warning(
                "OpenRouter rate limit warning: %d/%d calls used today, %d remaining.",
                _calls_today,
                _DAILY_LIMIT,
                calls_left,
            )


async def get_usage() -> dict:
    """
    Return current usage statistics for the OpenRouter daily quota.

    Returns:
        dict with keys: calls_today, limit, remaining, resets_at_utc.
    """
    async with _lock:
        _reset_if_new_day()
        remaining = max(0, _DAILY_LIMIT - _calls_today)
        return {
            "calls_today": _calls_today,
            "limit": _DAILY_LIMIT,
            "remaining": remaining,
            "resets_at_utc": _next_midnight_utc(),
        }
