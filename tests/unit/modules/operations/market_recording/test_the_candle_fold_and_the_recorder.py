"""`EPIC-047H` - a longer timeframe's forming candle is folded from the 1m ticks, and the recorder only listens.

Real `MarketTickEvent`s and the real `MemoryMarkBoard`; the clock is the only double.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.candle_fold import (
    CandleFold,
    MinuteTick,
    bucket_start,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.market_recorder import (
    FORGET_AFTER,
    MarketRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.trading.adapters.memory_mark_board import (
    MemoryMarkBoard,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

T0 = datetime(2026, 10, 27, 10, 0, tzinfo=UTC)
VENUE = TradingVenue.FUTURES_TESTNET
FIVE = TimeFrame.FIVE_MINUTES


class _Clock(IOperationsClock):
    def __init__(self) -> None:
        self.at = T0

    def now(self) -> datetime:
        return self.at


def _tick(minute: int, o: str, h: str, low: str, c: str, v: str = "1") -> MinuteTick:
    return MinuteTick(
        T0 + timedelta(minutes=minute),
        Decimal(o),
        Decimal(h),
        Decimal(low),
        Decimal(c),
        Decimal(v),
    )


def _event(
    minute: int, close: float, *, symbol: str = "BTCUSDT", interval: str = "1m"
) -> MarketTickEvent:
    opened = T0 + timedelta(minutes=minute)
    return MarketTickEvent(
        MarketData(
            symbol,
            interval,
            opened,
            close,
            close + 1,
            close - 1,
            close,
            2.0,
            opened + timedelta(minutes=1),
            0.0,
            0,
            0.0,
            0.0,
            is_closed=False,
        ),
        market_type=VENUE.market_type,
        market_data_venue=VENUE.market_data_venue,
    )


def test_a_bucket_starts_on_the_exchanges_own_grid() -> None:
    assert bucket_start(T0 + timedelta(minutes=7), FIVE) == T0 + timedelta(minutes=5)
    assert bucket_start(T0 + timedelta(minutes=59), TimeFrame.ONE_HOUR) == T0
    assert bucket_start(T0 + timedelta(hours=5), TimeFrame.ONE_DAY) == T0.replace(
        hour=0
    )


def test_five_minutes_of_1m_ticks_fold_into_one_candle() -> None:
    fold = CandleFold(FIVE)
    fold.add(_tick(0, "100", "105", "99", "104", "2"))
    fold.add(_tick(1, "104", "110", "103", "108", "3"))
    fold.add(
        _tick(1, "104", "112", "103", "109", "4")
    )  # the same minute again: it replaces itself
    fold.add(_tick(2, "109", "109", "95", "96", "5"))

    candle = fold.candle()

    assert candle is not None
    assert (candle.open_price, candle.high_price, candle.low_price) == (
        Decimal(100),
        Decimal(112),
        Decimal(95),
    )
    assert (candle.close_price, candle.volume) == (Decimal(96), Decimal(11))
    assert candle.open_time == T0
    assert candle.complete


def test_a_host_that_began_inside_the_bucket_says_the_candle_is_partial() -> None:
    fold = CandleFold(FIVE)
    fold.add(_tick(2, "100", "101", "99", "100"))

    candle = fold.candle()

    assert candle is not None
    assert not candle.complete


def test_the_next_bucket_starts_afresh_and_a_late_tick_changes_nothing() -> None:
    fold = CandleFold(FIVE)
    fold.add(_tick(0, "100", "105", "99", "104"))
    fold.add(_tick(5, "200", "201", "199", "200"))
    fold.add(_tick(4, "1", "999", "0.5", "1"))  # a tick of the old bucket, late

    candle = fold.candle()

    assert candle is not None
    assert (candle.open_time, candle.open_price, candle.high_price) == (
        T0 + timedelta(minutes=5),
        Decimal(200),
        Decimal(201),
    )


def test_a_timeframe_that_is_not_whole_minutes_is_refused() -> None:
    with pytest.raises(ValueError, match="whole number of minutes"):
        CandleFold(TimeFrame.ONE_SECOND)


def _recorder(clock: _Clock, marks: MemoryMarkBoard | None = None) -> MarketRecorder:
    return MarketRecorder(
        [TimeFrame.ONE_MINUTE, FIVE],
        lambda: [VENUE],
        marks or MemoryMarkBoard(lambda: clock.at),
        clock,
    )


def test_the_recorder_publishes_the_last_price_and_a_forming_candle_per_timeframe() -> (
    None
):
    clock = _Clock()
    recorder = _recorder(clock)

    recorder.on_tick(_event(0, 100.0))
    clock.at = T0 + timedelta(seconds=30)
    recorder.on_tick(_event(0, 101.0))

    (market,) = recorder.snapshot()
    assert (market.venue, market.symbol) == (VENUE, "BTCUSDT")
    assert market.last_price == Decimal("101.0")
    assert market.last_at == clock.at
    assert [c.timeframe for c in market.forming] == ["1m", "5m"]


def test_the_mark_the_exit_watch_read_is_published_with_when_the_host_recorded_it() -> (
    None
):
    clock = _Clock()
    marks = MemoryMarkBoard(lambda: clock.at)
    recorder = _recorder(clock, marks)
    recorder.on_tick(_event(0, 100.0))

    marks.record(VENUE, "BTCUSDT", Decimal("99.5"), T0)
    marks.record(
        VENUE, "ETHUSDT", Decimal(3000), T0
    )  # no stream for it: a mark alone is still published

    by_symbol = {m.symbol: m for m in recorder.snapshot()}
    assert by_symbol["BTCUSDT"].mark_price == Decimal("99.5")
    assert by_symbol["BTCUSDT"].mark_at == T0
    assert by_symbol["ETHUSDT"].last_price is None
    assert by_symbol["ETHUSDT"].mark_price == Decimal(3000)


def test_a_tick_of_another_interval_or_another_market_is_not_mixed_in() -> None:
    clock = _Clock()
    recorder = _recorder(clock)

    recorder.on_tick(_event(0, 100.0, interval="5m"))
    other = _event(0, 50.0)
    other.market_type = MarketType.SPOT
    recorder.on_tick(other)
    other.market_data_venue = MarketDataVenue.MAINNET_PUBLIC
    recorder.on_tick(other)

    assert recorder.snapshot() == ()


def test_a_symbol_silent_for_a_day_is_dropped_but_a_quiet_one_keeps_its_age() -> None:
    clock = _Clock()
    recorder = _recorder(clock)
    recorder.on_tick(_event(0, 100.0))

    clock.at = T0 + FORGET_AFTER - timedelta(seconds=1)
    (market,) = recorder.snapshot()
    assert market.last_at == T0, "the price keeps the moment it was received"

    clock.at = T0 + FORGET_AFTER
    assert recorder.snapshot() == ()
