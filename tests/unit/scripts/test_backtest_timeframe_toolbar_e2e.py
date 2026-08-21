"""Regression coverage for `_SeededMarketDataRepository`
(`scripts/backtest_timeframe_toolbar_e2e.py`) — a hand-rolled
`IMarketDataRepository` test double for the Desktop E2E probe.

Found by EPIC-002A's mypy baseline audit: this class had drifted 7 methods
behind the real interface (same defect class as BUG-026 — a Port gained
abstract methods and a hand-written implementer wasn't updated), so
instantiating it raised `TypeError: Can't instantiate abstract class`. Fixed
directly; this test proves the fix at the object level without needing a
real windowing session (the full probe is Windows Desktop E2E only, per its
own module docstring).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.scripts.backtest_timeframe_toolbar_e2e import (
    _SYMBOL,
    _SeededMarketDataRepository,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame


def _make_kline(open_time: datetime) -> MarketData:
    return MarketData(
        symbol=_SYMBOL,
        interval=TimeFrame.ONE_HOUR.value,
        open_time=open_time,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=105.0,
        volume=10.0,
        close_time=open_time + timedelta(hours=1),
        quote_asset_volume=1000.0,
        number_of_trades=5,
        taker_buy_base_asset_volume=5.0,
        taker_buy_quote_asset_volume=500.0,
    )


def test_instantiates_without_raising():
    """The original failure mode: `TypeError: Can't instantiate abstract
    class ... with abstract attributes ...` — raised at construction time,
    before any of the class's own logic ever ran."""
    _SeededMarketDataRepository([])


def test_count_klines_matches_get_klines_length():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    klines = [_make_kline(start + timedelta(hours=i)) for i in range(5)]
    repo = _SeededMarketDataRepository(klines)

    assert repo.count_klines(_SYMBOL, TimeFrame.ONE_HOUR) == 5


def test_stream_klines_yields_the_same_rows_as_get_klines():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    klines = [_make_kline(start + timedelta(hours=i)) for i in range(5)]
    repo = _SeededMarketDataRepository(klines)

    streamed = list(repo.stream_klines(_SYMBOL, TimeFrame.ONE_HOUR))
    fetched = repo.get_klines(_SYMBOL, TimeFrame.ONE_HOUR)

    assert [k.open_time for k in streamed] == [k.open_time for k in fetched]


def test_stream_klines_offset_and_limit():
    start = datetime(2026, 8, 1, tzinfo=UTC)
    klines = [_make_kline(start + timedelta(hours=i)) for i in range(5)]
    repo = _SeededMarketDataRepository(klines)

    tail = list(repo.stream_klines(_SYMBOL, TimeFrame.ONE_HOUR, offset=3, limit=2))

    assert [k.open_time for k in tail] == [
        start + timedelta(hours=3),
        start + timedelta(hours=4),
    ]


def test_stub_administrative_methods_are_harmless_no_ops():
    """`clear_klines`/`purge_all`/`vacuum`/`get_gaps` aren't exercised by the
    probe's own scenario (BUG-008 timeframe toolbar) — this only proves they
    exist and don't raise, matching the same-shaped stubs already
    established for `_InMemoryMarketDataRepository`
    (`tests/integration/presentation/test_backtest_user_flow.py`)."""
    repo = _SeededMarketDataRepository([])

    assert repo.clear_klines(_SYMBOL) == 0
    assert repo.purge_all() == 0
    assert repo.list_available_shards() == [_SYMBOL]
    assert repo.vacuum() is None
    assert repo.get_gaps(_SYMBOL, TimeFrame.ONE_HOUR) == []
