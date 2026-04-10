"""In-memory rate limiter for trial (non-invited) users."""
from __future__ import annotations

import time
from datetime import date


class RateLimiter:
    """Per-user rate limiting with per-minute burst and daily quota.

    Invited users (checked externally) bypass all limits.
    Fully in-memory — resets on restart, which is fine for a trial gate.
    """

    def __init__(
        self,
        rate_per_minute: int = 10,
        daily_quota: int = 50,
    ) -> None:
        self._rate_per_minute = rate_per_minute
        self._daily_quota = daily_quota
        # user_id → list of monotonic timestamps within the last 60s
        self._minute_window: dict[int, list[float]] = {}
        # "user_id:YYYY-MM-DD" → message count
        self._daily_counts: dict[str, int] = {}

    def check(self, user_id: int) -> tuple[bool, str]:
        """Check whether *user_id* may send a message.

        Returns ``(True, "")`` if allowed, or ``(False, reason)`` where
        *reason* is ``"rate_limit"`` or ``"daily_quota"``.
        """
        now = time.monotonic()
        today = date.today().isoformat()

        # --- daily quota ---
        day_key = f"{user_id}:{today}"
        daily = self._daily_counts.get(day_key, 0)
        if daily >= self._daily_quota:
            return False, "daily_quota"

        # --- per-minute burst ---
        timestamps = self._minute_window.get(user_id, [])
        recent = [ts for ts in timestamps if now - ts < 60.0]
        if len(recent) >= self._rate_per_minute:
            return False, "rate_limit"

        # Record (immutable-style rebuild)
        self._minute_window[user_id] = [*recent, now]
        self._daily_counts[day_key] = daily + 1
        return True, ""

    @property
    def rate_per_minute(self) -> int:
        return self._rate_per_minute

    @property
    def daily_quota(self) -> int:
        return self._daily_quota
