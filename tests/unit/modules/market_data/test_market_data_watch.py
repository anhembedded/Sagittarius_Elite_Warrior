"""`BUG-179` — `MarketDataWatch` counts what a test created, never what it inherited."""

from __future__ import annotations

from datetime import UTC, datetime

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.tests.market_data_watch import MarketDataWatch


def _market_data() -> MarketData:
    moment = datetime(2023, 1, 1, tzinfo=UTC)
    return MarketData(
        "BTCUSDT", "1m", moment, 1.0, 1.0, 1.0, 1.0, 1.0, moment, 1.0, 1, 1.0, 1.0
    )


def test_the_watch_ignores_market_data_that_existed_before_it_began() -> None:
    """What another test still held is not this test's to count, and releasing
    it must not make the count negative (the `-30` of `BUG-179`)."""
    held = [_market_data() for _ in range(30)]
    watch = MarketDataWatch()

    del held

    assert watch.new_live_count() == 0


def test_the_watch_counts_market_data_created_after_it_began_while_it_lives() -> None:
    watch = MarketDataWatch()
    kept = [_market_data() for _ in range(3)]

    assert watch.new_live_count() == 3

    del kept
    assert watch.new_live_count() == 0
