"""Async retry decorator for external service calls (Telegram API, LLM, HTTP).

Supports three backoff strategies:
  - exponential: delay * backoff^attempt (default)
  - fixed: constant delay between retries
  - jitter: exponential + random jitter to avoid thundering herd
"""
from __future__ import annotations

import asyncio
import functools
import logging
import random
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class BackoffStrategy(str, Enum):
    EXPONENTIAL = "exponential"
    FIXED = "fixed"
    JITTER = "jitter"


def _compute_wait(
    strategy: BackoffStrategy,
    delay: float,
    backoff: float,
    attempt: int,
) -> float:
    """Compute wait time based on strategy (attempt is 0-indexed)."""
    if strategy == BackoffStrategy.FIXED:
        return delay
    base = delay * (backoff ** attempt)
    if strategy == BackoffStrategy.JITTER:
        return base * (0.5 + random.random())  # noqa: S311 — not crypto
    return base


def with_retry(
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    strategy: BackoffStrategy | str = BackoffStrategy.JITTER,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """Decorator that retries an async function on failure.

    Args:
        max_retries: Total attempts (including the first call).
        delay: Base delay in seconds.
        backoff: Multiplier for exponential/jitter strategies.
        strategy: "exponential", "fixed", or "jitter" (default).
        exceptions: Exception types to catch and retry on.

    Usage::

        @with_retry(max_retries=3, delay=0.5, strategy="jitter")
        async def send_message(chat_id: int, text: str) -> MessageRef:
            ...
    """
    strat = BackoffStrategy(strategy) if isinstance(strategy, str) else strategy

    def decorator(fn: F) -> F:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries):
                try:
                    return await fn(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt + 1 >= max_retries:
                        break
                    wait = _compute_wait(strat, delay, backoff, attempt)
                    logger.debug(
                        "[retry] %s attempt %d/%d failed (%.2fs backoff): %s",
                        fn.__qualname__, attempt + 1, max_retries, wait, exc,
                    )
                    await asyncio.sleep(wait)
            logger.warning(
                "[retry] %s failed after %d attempts: %s",
                fn.__qualname__, max_retries, last_exc,
                exc_info=True,
            )
            raise last_exc  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator
