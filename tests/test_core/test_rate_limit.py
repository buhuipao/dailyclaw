"""Tests for src/core/rate_limit.py."""
from __future__ import annotations

import pytest

from src.core.rate_limit import RateLimiter


class TestRateLimiter:
    def test_allows_messages_under_limits(self):
        rl = RateLimiter(rate_per_minute=3, daily_quota=10)
        allowed, reason = rl.check(user_id=1)
        assert allowed is True
        assert reason == ""

    def test_blocks_after_per_minute_burst(self):
        rl = RateLimiter(rate_per_minute=2, daily_quota=100)
        rl.check(user_id=1)
        rl.check(user_id=1)
        allowed, reason = rl.check(user_id=1)
        assert allowed is False
        assert reason == "rate_limit"

    def test_blocks_after_daily_quota(self):
        rl = RateLimiter(rate_per_minute=100, daily_quota=3)
        rl.check(user_id=1)
        rl.check(user_id=1)
        rl.check(user_id=1)
        allowed, reason = rl.check(user_id=1)
        assert allowed is False
        assert reason == "daily_quota"

    def test_separate_users_have_separate_limits(self):
        rl = RateLimiter(rate_per_minute=1, daily_quota=100)
        rl.check(user_id=1)
        # User 1 is rate-limited
        allowed1, _ = rl.check(user_id=1)
        assert allowed1 is False
        # User 2 is fine
        allowed2, _ = rl.check(user_id=2)
        assert allowed2 is True

    def test_daily_quota_checked_before_rate(self):
        """When both limits are exceeded, daily_quota takes precedence."""
        rl = RateLimiter(rate_per_minute=2, daily_quota=2)
        rl.check(user_id=1)
        rl.check(user_id=1)
        allowed, reason = rl.check(user_id=1)
        assert allowed is False
        assert reason == "daily_quota"

    def test_properties_expose_config(self):
        rl = RateLimiter(rate_per_minute=7, daily_quota=42)
        assert rl.rate_per_minute == 7
        assert rl.daily_quota == 42
