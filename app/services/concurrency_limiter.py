"""Limits how many extractions run at once and how many may wait for their turn."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.exceptions import ServiceBusyError


class ConcurrencyLimiter:
    def __init__(self, max_concurrent: int, max_waiting: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._capacity = max_concurrent + max_waiting
        self._pending = 0

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        if self._pending >= self._capacity:
            raise ServiceBusyError()
        self._pending += 1
        try:
            async with self._semaphore:
                yield
        finally:
            self._pending -= 1
