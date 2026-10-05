"""`ChartHistory` (`EPIC-033S`): the window before the oldest drawn candle
joins it with neither a gap nor a duplicate, and a range is exactly the
candles that open in it. Boundary values at the window's edge and the
range's ends, against the verified in-memory store."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    T0,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market import chart_history
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.chart_history import (
    ChartHistory,
    HistoryRange,
)

_MINUTE = TimeFrame.ONE_MINUTE
_SPOT = MarketType.SPOT


def _store(minutes: range, market: MarketType = _SPOT) -> FakeHistoricalKlines:
    store = FakeHistoricalKlines()
    store.seed([candle("BTCUSDT", minute) for minute in minutes], market)
    return store


def _minutes(candles) -> list[int]:
    return [int((k.open_time - T0).total_seconds() // 60) for k in candles]


# -- the window before the oldest drawn candle --------------------------------


def test_the_older_window_ends_right_before_the_oldest_drawn_candle():
    history = ChartHistory(_store(range(1000)), _SPOT, window=500)

    older = history.older_than("BTCUSDT", _MINUTE, candle("BTCUSDT", 500))

    assert _minutes(older) == list(range(500))


@pytest.mark.parametrize(
    ("oldest", "expected"),
    [
        (10, [7, 8, 9]),  # more stored than the window: the newest three
        (3, [0, 1, 2]),  # exactly the window
        (2, [0, 1]),  # fewer than the window: all there is
        (0, []),  # the oldest stored candle is drawn: nothing older
    ],
)
def test_the_older_window_at_the_edge_of_what_is_stored(oldest, expected):
    history = ChartHistory(_store(range(20)), _SPOT, window=3)

    older = history.older_than("BTCUSDT", _MINUTE, candle("BTCUSDT", oldest))

    assert _minutes(older) == expected


def test_a_gap_the_store_has_stays_and_no_candle_is_invented():
    stored = [minute for minute in range(20) if minute != 9]
    store = FakeHistoricalKlines()
    store.seed([candle("BTCUSDT", minute) for minute in stored])
    history = ChartHistory(store, _SPOT, window=3)

    older = history.older_than("BTCUSDT", _MINUTE, candle("BTCUSDT", 10))

    assert _minutes(older) == [6, 7, 8]


def test_the_older_window_reads_only_its_own_market():
    store = _store(range(5, 10))
    store.seed(
        [candle("BTCUSDT", minute) for minute in range(10)], MarketType.FUTURES_USD_M
    )
    history = ChartHistory(store, _SPOT, window=10)

    older = history.older_than("BTCUSDT", _MINUTE, candle("BTCUSDT", 8))

    assert _minutes(older) == [5, 6, 7]
    assert {read.market for read in store.reads} == {_SPOT}


# -- a chosen range -------------------------------------------------------------


def _at(minute: int, seconds: int = 0) -> datetime:
    return T0 + timedelta(minutes=minute, seconds=seconds)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (_at(10), _at(20), list(range(10, 21))),  # both ends included
        (_at(10, 1), _at(20), list(range(11, 21))),  # just after an open
        (_at(10), _at(19, 59), list(range(10, 20))),  # just before an open
        (_at(-5), _at(2), [0, 1, 2]),  # starts before the store does
    ],
)
def test_a_range_is_every_candle_that_opens_in_it(start, end, expected):
    history = ChartHistory(_store(range(30)), _SPOT)

    found = history.in_range("BTCUSDT", _MINUTE, HistoryRange(start, end))

    assert _minutes(found.candles) == expected
    assert found.cut is False


def test_a_range_longer_than_the_limit_keeps_its_newest_and_says_so(monkeypatch):
    monkeypatch.setattr(chart_history, "RANGE_CANDLE_LIMIT", 5)
    history = ChartHistory(_store(range(30)), _SPOT)

    longer = history.in_range("BTCUSDT", _MINUTE, HistoryRange(_at(10), _at(20)))
    exact = history.in_range("BTCUSDT", _MINUTE, HistoryRange(_at(10), _at(14)))

    assert _minutes(longer.candles) == [16, 17, 18, 19, 20]
    assert longer.cut is True
    assert _minutes(exact.candles) == [10, 11, 12, 13, 14]
    assert exact.cut is False


def test_a_range_is_in_utc_and_ends_after_it_starts():
    with pytest.raises(ValueError, match="UTC"):
        HistoryRange(_at(0).replace(tzinfo=None), _at(5))
    with pytest.raises(ValueError, match="ends after it starts"):
        HistoryRange(_at(5), _at(5))
