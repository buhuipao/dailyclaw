"""Tests for the retry decorator."""
from __future__ import annotations

import pytest

from src.core.retry import BackoffStrategy, _compute_wait, with_retry


class TestComputeWait:
    def test_fixed_always_returns_delay(self):
        for attempt in range(5):
            assert _compute_wait(BackoffStrategy.FIXED, 1.0, 2.0, attempt) == 1.0

    def test_exponential_doubles(self):
        assert _compute_wait(BackoffStrategy.EXPONENTIAL, 1.0, 2.0, 0) == 1.0
        assert _compute_wait(BackoffStrategy.EXPONENTIAL, 1.0, 2.0, 1) == 2.0
        assert _compute_wait(BackoffStrategy.EXPONENTIAL, 1.0, 2.0, 2) == 4.0

    def test_jitter_within_range(self):
        """Jitter should be between 0.5x and 1.5x of the exponential base."""
        for attempt in range(5):
            base = 1.0 * (2.0 ** attempt)
            for _ in range(20):
                wait = _compute_wait(BackoffStrategy.JITTER, 1.0, 2.0, attempt)
                assert base * 0.5 <= wait <= base * 1.5


class TestWithRetry:
    @pytest.mark.asyncio
    async def test_succeeds_first_try(self):
        call_count = 0

        @with_retry(max_retries=3, delay=0.01)
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert await fn() == "ok"
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_retries_then_succeeds(self):
        call_count = 0

        @with_retry(max_retries=3, delay=0.01, strategy="fixed")
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("fail")
            return "ok"

        assert await fn() == "ok"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_exhaustion(self):
        call_count = 0

        @with_retry(max_retries=2, delay=0.01)
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("always fails")

        with pytest.raises(ConnectionError, match="always fails"):
            await fn()
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_only_catches_specified_exceptions(self):
        call_count = 0

        @with_retry(max_retries=3, delay=0.01, exceptions=(ConnectionError,))
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("wrong type")

        with pytest.raises(ValueError):
            await fn()
        assert call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_strategy(self):
        call_count = 0

        @with_retry(max_retries=3, delay=0.01, strategy="exponential")
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("retry me")
            return "done"

        assert await fn() == "done"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_jitter_strategy(self):
        call_count = 0

        @with_retry(max_retries=3, delay=0.01, strategy="jitter")
        async def fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("retry me")
            return "done"

        assert await fn() == "done"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_preserves_function_name(self):
        @with_retry(max_retries=2, delay=0.01)
        async def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    @pytest.mark.asyncio
    async def test_passes_args_and_kwargs(self):
        @with_retry(max_retries=2, delay=0.01)
        async def add(a: int, b: int, extra: int = 0) -> int:
            return a + b + extra

        assert await add(1, 2) == 3
        assert await add(1, 2, extra=10) == 13

    @pytest.mark.asyncio
    async def test_strategy_string_alias(self):
        """Strategy can be passed as a plain string."""
        @with_retry(max_retries=2, delay=0.01, strategy="fixed")
        async def fn() -> str:
            return "ok"

        assert await fn() == "ok"
