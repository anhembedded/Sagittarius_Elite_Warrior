"""`EPIC-035A` — the two time ports a price watch stands on, fake and real.

`IMonotonicClock` is what staleness is measured on: it never goes backwards
and, unlike `IBotClock`, carries no date, so a wall-clock step cannot move it.
`IBotTicker` is the periodic trigger; the fake fires on demand and the real
one fires on its own thread, and both honour the same three promises.
"""

from __future__ import annotations

import logging
import threading

import pytest
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.system_monotonic_clock import (
    SystemMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.adapters.thread_bot_ticker import (
    ThreadBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_bot_ticker import (
    FakeBotTicker,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.fake_monotonic_clock import (
    FakeMonotonicClock,
)


class MonotonicClockContract:
    @pytest.fixture
    def impl(self) -> IMonotonicClock:
        raise NotImplementedError

    def test_it_never_goes_backwards(self, impl: IMonotonicClock) -> None:
        first = impl.seconds()
        assert impl.seconds() >= first


class TestFakeMonotonicClock(MonotonicClockContract):
    @pytest.fixture
    def impl(self) -> IMonotonicClock:
        return FakeMonotonicClock()


class TestSystemMonotonicClock(MonotonicClockContract):
    @pytest.fixture
    def impl(self) -> IMonotonicClock:
        return SystemMonotonicClock()


def test_advance_moves_the_fake_forward_by_exactly_that_much() -> None:
    clock = FakeMonotonicClock()
    before = clock.seconds()
    clock.advance(42.5)
    assert clock.seconds() == before + 42.5


def test_the_fake_ticker_runs_the_task_each_time_it_fires() -> None:
    ticker = FakeBotTicker()
    calls: list[str] = []
    ticker.every(5.0, lambda: calls.append("tick"))

    ticker.fire()
    ticker.fire()

    assert calls == ["tick", "tick"]
    assert ticker.interval == 5.0


def test_the_fake_ticker_stops_firing_once_closed() -> None:
    ticker = FakeBotTicker()
    calls: list[str] = []
    ticker.every(5.0, lambda: calls.append("tick"))

    ticker.close()
    ticker.fire()

    assert calls == []
    assert ticker.closed is True


def test_the_real_ticker_runs_the_task_repeatedly_and_stops_on_close() -> None:
    ticker = ThreadBotTicker("test-ticker")
    ran = threading.Semaphore(0)
    ticker.every(0.01, ran.release)

    assert ran.acquire(timeout=5.0)
    assert ran.acquire(timeout=5.0)
    ticker.close()

    while ran.acquire(blocking=False):
        pass
    assert not ran.acquire(timeout=0.1), "a closed ticker fires no more"


def test_the_real_ticker_survives_a_task_that_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ticker = ThreadBotTicker("test-ticker-raising")
    attempts = threading.Semaphore(0)

    def failing() -> None:
        attempts.release()
        raise RuntimeError("a bad check")

    with caplog.at_level(logging.ERROR, logger="App.Bots.Ticker"):
        ticker.every(0.01, failing)
        try:
            assert attempts.acquire(timeout=5.0)
            assert attempts.acquire(timeout=5.0), "the next tick still comes"
        finally:
            ticker.close()

    assert any("a tick raised" in record.getMessage() for record in caplog.records)


def test_closing_a_ticker_twice_is_harmless() -> None:
    ticker = ThreadBotTicker("test-ticker-twice")
    ticker.every(0.01, lambda: None)
    ticker.close()
    ticker.close()
