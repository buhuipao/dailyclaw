"""Tests for src/adapters/telegram.py — DynamicAuthFilter only.

We deliberately avoid testing TelegramAdapter.start/stop or anything
that requires a real Telegram connection.
"""
from __future__ import annotations

import pytest

from src.adapters.telegram import DynamicAuthFilter


# ---------------------------------------------------------------------------
# DynamicAuthFilter
# ---------------------------------------------------------------------------


class TestDynamicAuthFilter:
    def test_admin_ids_always_authorized(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[111, 222])
        assert auth.is_authorized(111) is True
        assert auth.is_authorized(222) is True

    def test_unknown_user_not_authorized(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[111])
        assert auth.is_authorized(999) is False

    def test_db_users_authorized_after_cache_update(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[])
        assert auth.is_authorized(42) is False
        auth.update_cache({42, 99})
        assert auth.is_authorized(42) is True
        assert auth.is_authorized(99) is True

    def test_db_users_replaced_on_update(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[])
        auth.update_cache({10, 20})
        auth.update_cache({30})
        assert auth.is_authorized(10) is False
        assert auth.is_authorized(30) is True

    def test_admin_ids_property_returns_set_copy(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[5, 6])
        ids = auth.admin_ids
        assert isinstance(ids, set)
        # Mutating the returned set must not affect internal state
        ids.add(999)
        assert auth.is_authorized(999) is False

    def test_admin_ids_property_contains_all_admins(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[1, 2, 3])
        assert auth.admin_ids == {1, 2, 3}

    def test_admin_always_authorized_regardless_of_cache(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[7])
        auth.update_cache(set())  # empty cache
        assert auth.is_authorized(7) is True

    def test_empty_admin_list(self) -> None:
        auth = DynamicAuthFilter(admin_ids=[])
        assert auth.is_authorized(0) is False
        assert auth.admin_ids == set()
