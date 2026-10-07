"""Limits how many extractions run at once and how many may wait for their turn."""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from app.exceptions import ServiceBusyError


class ConcurrencyLimiter:
    """Admits up to ``max_concurrent`` tasks at once and queues up to ``max_waiting`` more, in arrival order.

    Anything beyond that is rejected immediately with ServiceBusyError instead of
    waiting longer than the client is willing to (backpressure). One instance must
    be shared per process; it relies on a single event loop, so it needs no locks.
    """

    def __init__(self, max_concurrent: int, max_waiting: int) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._capacity = max_concurrent + max_waiting
        self._pending = 0  # running + waiting

    @asynccontextmanager
    async def slot(self) -> AsyncIterator[None]:
        """Hold one running slot for the duration of the ``async with`` block, waiting for it if needed.

        Raises:
            ServiceBusyError: if every running and waiting place is already taken.
        """
        if self._pending >= self._capacity:
            raise ServiceBusyError()
        self._pending += 1
        try:
            async with self._semaphore:
                yield
        finally:
            self._pending -= 1
