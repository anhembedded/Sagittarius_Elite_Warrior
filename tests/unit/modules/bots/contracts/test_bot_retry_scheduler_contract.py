"""`EPIC-035C` — both retry schedulers pass the scheduler's contract; the fake's helper is verified."""

from __future__ import annotations

import threading
from collections.abc import Callable, Iterator
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.timer_bot_retry_scheduler import (
    TimerBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_retry_scheduler import (
    BotRetrySchedulerContract,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_retry_scheduler import (
    FakeBotRetryScheduler,
)


class TestFakeBotRetryScheduler(BotRetrySchedulerContract):
    @pytest.fixture
    def impl(self) -> IBotRetryScheduler:
        return FakeBotRetryScheduler()

    @pytest.fixture
    def release(self, impl: IBotRetryScheduler) -> Callable[[], None]:
        assert isinstance(impl, FakeBotRetryScheduler)
        fake = impl

        def run_all() -> None:
            while fake.pending:
                fake.run_next()

        return run_all


class TestTimerBotRetryScheduler(BotRetrySchedulerContract):
    @pytest.fixture
    def impl(self) -> Iterator[IBotRetryScheduler]:
        scheduler = TimerBotRetryScheduler()
        yield scheduler
        scheduler.close()

    @pytest.fixture
    def release(self, impl: IBotRetryScheduler) -> Callable[[], None]:
        def join_every_timer() -> None:
            # A due timer ends once its task ran and a cancelled one ends at
            # once, so joining the live timers waits on exactly the tasks that
            # were going to run.
            for thread in threading.enumerate():
                if isinstance(thread, threading.Timer):
                    thread.join(timeout=5)

        return join_every_timer


def test_run_next_runs_the_oldest_pending_retry_first() -> None:
    scheduler = FakeBotRetryScheduler()
    order: list[str] = []
    scheduler.after(timedelta(seconds=10), lambda: order.append("first"))
    scheduler.after(timedelta(seconds=30), lambda: order.append("second"))

    scheduler.run_next()

    assert order == ["first"]
    assert [retry.delay for retry in scheduler.pending] == [timedelta(seconds=30)]
