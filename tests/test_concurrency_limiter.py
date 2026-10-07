"""Unit tests for the concurrency limiter that applies backpressure to extractions."""
import asyncio

import pytest

from app.exceptions import ServiceBusyError
from app.services.concurrency_limiter import ConcurrencyLimiter

pytestmark = pytest.mark.asyncio

TIMEOUT_S = 1


async def _hold_slot(limiter: ConcurrencyLimiter, entered: asyncio.Event, release: asyncio.Event) -> None:
    async with limiter.slot():
        entered.set()
        await release.wait()


class TestConcurrencyLimiter:
    async def test_runs_up_to_max_concurrent_at_once(self):
        limiter = ConcurrencyLimiter(max_concurrent=2, max_waiting=0)
        release = asyncio.Event()
        entered = [asyncio.Event(), asyncio.Event()]
        tasks = [asyncio.create_task(_hold_slot(limiter, event, release)) for event in entered]

        await asyncio.wait_for(asyncio.gather(*(event.wait() for event in entered)), TIMEOUT_S)

        release.set()
        await asyncio.gather(*tasks)

    async def test_extra_request_waits_its_turn_while_the_queue_has_room(self):
        limiter = ConcurrencyLimiter(max_concurrent=1, max_waiting=1)
        release, first, second = asyncio.Event(), asyncio.Event(), asyncio.Event()
        first_task = asyncio.create_task(_hold_slot(limiter, first, release))
        await first.wait()

        second_task = asyncio.create_task(_hold_slot(limiter, second, release))
        await asyncio.sleep(0.05)
        assert not second.is_set()

        release.set()
        await asyncio.wait_for(asyncio.gather(first_task, second_task), TIMEOUT_S)
        assert second.is_set()

    async def test_rejects_when_running_and_waiting_places_are_full(self):
        limiter = ConcurrencyLimiter(max_concurrent=1, max_waiting=1)
        release, first = asyncio.Event(), asyncio.Event()
        running = asyncio.create_task(_hold_slot(limiter, first, release))
        await first.wait()
        waiting = asyncio.create_task(_hold_slot(limiter, asyncio.Event(), release))
        await asyncio.sleep(0)

        with pytest.raises(ServiceBusyError):
            async with limiter.slot():
                pass

        release.set()
        await asyncio.gather(running, waiting)

    async def test_frees_the_slot_when_the_work_fails(self):
        limiter = ConcurrencyLimiter(max_concurrent=1, max_waiting=0)

        with pytest.raises(ValueError):
            async with limiter.slot():
                raise ValueError("extraction failed")

        async with limiter.slot():  # raises ServiceBusyError if the slot leaked
            pass
