"""`BUG-177` — `MarketDataCandleFeed.load_older`: the window before a chart's
oldest candle, from the store when it holds a full one, else fetched from the
chart's own market first, and joined to the drawn candles with neither a gap
nor a duplicate.

The exchange is a fake `IMarketDataSync` that stores what the span asked for
holds, as the real sync writes the candles the exchange returns (an upsert), so
what is read back is what was fetched.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.market_data_candle_feed import (
    MarketDataCandleFeed,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    T0,
    at,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    OlderCandlesRequest,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.market_data.contracts.fake_exchange_sync import (
    FakeExchangeSync,
)

_MINUTE = TimeFrame.ONE_MINUTE
_SPOT = MarketType.SPOT
_never: Callable[[], bool] = lambda: False


def _feed(
    stored: range,
    exchange: range = range(0),
    market: MarketType = _SPOT,
) -> tuple[MarketDataCandleFeed, FakeHistoricalKlines, FakeExchangeSync]:
    store = FakeHistoricalKlines()
    store.seed([candle("BTCUSDT", minute) for minute in stored], market)
    sync = FakeExchangeSync(
        store, [candle("BTCUSDT", minute) for minute in exchange], market
    )
    return MarketDataCandleFeed(sync, store, FakeMarketStream(), market), store, sync


def _older(feed: MarketDataCandleFeed, before_minute: int, limit: int) -> list[int]:
    request = OlderCandlesRequest("BTCUSDT", _MINUTE, at(before_minute), limit)
    rows = feed.load_older(request, _never)
    return [int((k.open_time - T0).total_seconds() // 60) for k in rows]


def test_a_full_stored_window_is_read_without_asking_the_exchange() -> None:
    feed, _store, sync = _feed(stored=range(1000))

    assert _older(feed, before_minute=500, limit=500) == list(range(500))
    assert sync.requests == []


@pytest.mark.parametrize(
    ("before", "expected"),
    [
        (10, [7, 8, 9]),  # more stored than the window: the newest three
        (3, [0, 1, 2]),  # exactly the window
    ],
)
def test_the_window_ends_right_before_the_oldest_drawn_candle(before, expected) -> None:
    feed, _store, sync = _feed(stored=range(20))

    assert _older(feed, before, limit=3) == expected
    assert sync.requests == []


def test_a_short_store_is_completed_from_the_exchange_and_stored() -> None:
    """The store holds minutes 8–19 only; the chart's oldest candle is minute
    10 and it wants 5: the exchange has 0–19, so 5–9 come back, and 5–7 are
    stored now (what a restart would read)."""
    feed, store, sync = _feed(stored=range(8, 20), exchange=range(20))

    assert _older(feed, before_minute=10, limit=5) == [5, 6, 7, 8, 9]

    assert len(sync.requests) == 1
    request = sync.requests[0]
    assert (request.start_time, request.end_time) == (at(5), at(10))
    assert request.market is _SPOT
    stored = store.load(_SPOT, "BTCUSDT", _MINUTE)
    assert [k.open_time for k in stored][:3] == [at(5), at(6), at(7)]


def test_an_empty_store_is_filled_from_the_exchange() -> None:
    feed, _store, sync = _feed(stored=range(0), exchange=range(100, 160))

    assert _older(feed, before_minute=130, limit=20) == list(range(110, 130))
    assert len(sync.requests) == 1


def test_no_candle_is_returned_twice_or_at_the_oldest_drawn_one() -> None:
    feed, _store, _sync = _feed(stored=range(8, 12), exchange=range(20))

    minutes = _older(feed, before_minute=10, limit=6)

    assert minutes == sorted(set(minutes))
    assert 10 not in minutes
    assert minutes == [4, 5, 6, 7, 8, 9]


def test_the_start_of_the_market_is_an_empty_window_not_an_error() -> None:
    feed, _store, sync = _feed(stored=range(5, 10), exchange=range(5, 10))

    assert _older(feed, before_minute=5, limit=10) == []
    assert len(sync.requests) == 1


def test_a_gap_the_market_has_stays_and_no_candle_is_invented() -> None:
    present = [minute for minute in range(20) if minute != 9]
    store = FakeHistoricalKlines()
    store.seed([candle("BTCUSDT", minute) for minute in present])
    sync = FakeExchangeSync(store, [candle("BTCUSDT", m) for m in present], _SPOT)
    feed = MarketDataCandleFeed(sync, store, FakeMarketStream(), _SPOT)

    assert _older(feed, before_minute=10, limit=3) == [6, 7, 8]


def test_the_exchange_is_the_feeds_own_market_and_its_cancellation_is_passed() -> None:
    market = MarketType.FUTURES_USD_M
    feed, store, sync = _feed(stored=range(0), exchange=range(30), market=market)
    feed.load_older(OlderCandlesRequest("BTCUSDT", _MINUTE, at(20), 5), _never)

    assert sync.requests[0].market is market
    assert sync.requests[0].cancellation_requested is _never
    assert {read.market for read in store.reads} == {market}


def test_a_sync_that_fails_is_raised_to_the_caller() -> None:
    class Refusing(IMarketDataSync):
        def sync(self, request: MarketDataSyncRequest) -> None:
            raise RuntimeError("exchange unreachable")

    feed = MarketDataCandleFeed(
        Refusing(), FakeHistoricalKlines(), FakeMarketStream(), _SPOT
    )

    with pytest.raises(RuntimeError, match="exchange unreachable"):
        feed.load_older(OlderCandlesRequest("BTCUSDT", _MINUTE, at(5), 3), _never)
