"""Scheduler abstraction — decoupled from any specific bot framework."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import time
from typing import Any


class Scheduler(ABC):
    @abstractmethod
    async def run_daily(
        self,
        callback: Callable,
        time: time,
        name: str,
        *,
        days: tuple[int, ...] | None = None,
        data: Any = None,
    ) -> None: ...

    @abstractmethod
    async def run_repeating(
        self,
        callback: Callable,
        interval: float,
        name: str,
        *,
        first: float = 0,
    ) -> None: ...

    @abstractmethod
    async def cancel(self, name: str) -> None: ...
