"""Tests for the Scheduler ABC."""
from __future__ import annotations

import asyncio
from datetime import time
from typing import Any

import pytest

from src.core.scheduler import Scheduler


# ---------------------------------------------------------------------------
# Concrete implementation for testing
# ---------------------------------------------------------------------------

class _Job:
    """Immutable job record."""

    __slots__ = ("callback", "time", "days", "data", "interval", "first", "kind")

    def __init__(
        self,
        *,
        kind: str,
        callback: Any,
        time: time | None = None,
        days: tuple[int, ...] | None = None,
        data: Any = None,
        interval: float | None = None,
        first: float = 0,
    ) -> None:
        self.kind = kind
        self.callback = callback
        self.time = time
        self.days = days
        self.data = data
        self.interval = interval
        self.first = first


class ConcreteScheduler(Scheduler):
    """In-memory scheduler used for unit tests."""

    def __init__(self) -> None:
        self._jobs: dict[str, _Job] = {}

    async def run_daily(
        self,
        callback: Any,
        time: time,
        name: str,
        *,
        days: tuple[int, ...] | None = None,
        data: Any = None,
    ) -> None:
        self._jobs = {
            **self._jobs,
            name: _Job(kind="daily", callback=callback, time=time, days=days, data=data),
        }

    async def run_repeating(
        self,
        callback: Any,
        interval: float,
        name: str,
        *,
        first: float = 0,
    ) -> None:
        self._jobs = {
            **self._jobs,
            name: _Job(kind="repeating", callback=callback, interval=interval, first=first),
        }

    async def cancel(self, name: str) -> None:
        self._jobs = {k: v for k, v in self._jobs.items() if k != name}

    def get_job(self, name: str) -> _Job | None:
        return self._jobs.get(name)

    def has_job(self, name: str) -> bool:
        return name in self._jobs


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def run(coro: Any) -> Any:
    return asyncio.get_event_loop().run_until_complete(coro)


async def _noop() -> None:
    pass


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchedulerIsAbstract:
    def test_cannot_instantiate_abc(self) -> None:
        with pytest.raises(TypeError):
            Scheduler()  # type: ignore[abstract]


class TestRunDaily:
    def setup_method(self) -> None:
        self.scheduler = ConcreteScheduler()

    def test_stores_job_by_name(self) -> None:
        t = time(8, 0)
        run(self.scheduler.run_daily(_noop, t, "morning"))
        assert self.scheduler.has_job("morning")

    def test_stores_time(self) -> None:
        t = time(9, 30)
        run(self.scheduler.run_daily(_noop, t, "standup"))
        job = self.scheduler.get_job("standup")
        assert job is not None
        assert job.time == t

    def test_defaults_days_to_none(self) -> None:
        run(self.scheduler.run_daily(_noop, time(7, 0), "alarm"))
        job = self.scheduler.get_job("alarm")
        assert job is not None
        assert job.days is None

    def test_stores_days_parameter(self) -> None:
        weekdays = (0, 1, 2, 3, 4)
        run(self.scheduler.run_daily(_noop, time(9, 0), "weekday_job", days=weekdays))
        job = self.scheduler.get_job("weekday_job")
        assert job is not None
        assert job.days == weekdays

    def test_stores_data_parameter(self) -> None:
        payload = {"chat_id": 42, "msg": "hello"}
        run(self.scheduler.run_daily(_noop, time(10, 0), "data_job", data=payload))
        job = self.scheduler.get_job("data_job")
        assert job is not None
        assert job.data == payload

    def test_stores_callback(self) -> None:
        run(self.scheduler.run_daily(_noop, time(6, 0), "cb_job"))
        job = self.scheduler.get_job("cb_job")
        assert job is not None
        assert job.callback is _noop

    def test_overwrite_same_name(self) -> None:
        run(self.scheduler.run_daily(_noop, time(6, 0), "job"))
        run(self.scheduler.run_daily(_noop, time(7, 0), "job"))
        job = self.scheduler.get_job("job")
        assert job is not None
        assert job.time == time(7, 0)


class TestRunRepeating:
    def setup_method(self) -> None:
        self.scheduler = ConcreteScheduler()

    def test_stores_job_by_name(self) -> None:
        run(self.scheduler.run_repeating(_noop, 60.0, "heartbeat"))
        assert self.scheduler.has_job("heartbeat")

    def test_stores_interval(self) -> None:
        run(self.scheduler.run_repeating(_noop, 30.0, "tick"))
        job = self.scheduler.get_job("tick")
        assert job is not None
        assert job.interval == 30.0

    def test_defaults_first_to_zero(self) -> None:
        run(self.scheduler.run_repeating(_noop, 10.0, "quick"))
        job = self.scheduler.get_job("quick")
        assert job is not None
        assert job.first == 0

    def test_stores_first_parameter(self) -> None:
        run(self.scheduler.run_repeating(_noop, 10.0, "delayed", first=5.0))
        job = self.scheduler.get_job("delayed")
        assert job is not None
        assert job.first == 5.0

    def test_stores_callback(self) -> None:
        run(self.scheduler.run_repeating(_noop, 1.0, "cb_rep"))
        job = self.scheduler.get_job("cb_rep")
        assert job is not None
        assert job.callback is _noop


class TestCancel:
    def setup_method(self) -> None:
        self.scheduler = ConcreteScheduler()

    def test_cancel_removes_daily_job(self) -> None:
        run(self.scheduler.run_daily(_noop, time(8, 0), "to_cancel"))
        assert self.scheduler.has_job("to_cancel")
        run(self.scheduler.cancel("to_cancel"))
        assert not self.scheduler.has_job("to_cancel")

    def test_cancel_removes_repeating_job(self) -> None:
        run(self.scheduler.run_repeating(_noop, 60.0, "rep_cancel"))
        run(self.scheduler.cancel("rep_cancel"))
        assert not self.scheduler.has_job("rep_cancel")

    def test_cancel_nonexistent_job_is_noop(self) -> None:
        run(self.scheduler.cancel("ghost"))  # should not raise

    def test_cancel_only_removes_named_job(self) -> None:
        run(self.scheduler.run_daily(_noop, time(8, 0), "keep"))
        run(self.scheduler.run_daily(_noop, time(9, 0), "remove"))
        run(self.scheduler.cancel("remove"))
        assert self.scheduler.has_job("keep")
        assert not self.scheduler.has_job("remove")
