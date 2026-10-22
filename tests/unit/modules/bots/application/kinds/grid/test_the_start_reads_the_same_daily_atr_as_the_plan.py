"""`BOT-227` - the Plan and the Start read one daily ATR from the stored candles, or say why not.

@details The Start used to pass no ATR, so the stop-to-liquidation floor could only be the flat
share there. `DailyAtrReader` is read by the planner's query and by `FuturesStartReads`; an ATR is
not offered from too few candles or from candles that stopped arriving, and the Start then falls
back to the owner's flat floor and logs why.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.daily_atr_reader import (
    MAX_DAILY_CANDLE_AGE,
    DailyAtrReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_start_checks import (
    FuturesStartReads,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_thresholds import (
    FuturesGridThresholds,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.candles import (
    T0,
    candle,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_historical_klines import (
    FakeHistoricalKlines,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_data_sources import (
    FakeMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.bots.application.services.grid_world import (
    SYMBOL,
    grid_world,
)

VENUE = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET
_DAYS = 30


def _sources(
    days: int = _DAYS,
    venue: TradingVenue = VENUE,
    market: MarketType = MarketType.FUTURES_USD_M,
) -> FakeMarketDataSources:
    klines = FakeHistoricalKlines()
    klines.seed(
        [
            candle(
                SYMBOL,
                minutes=day * 1440,
                interval=TimeFrame.ONE_DAY,
                close_price=99.0 + 2 * (day % 2),
            )
            for day in range(days)
        ],
        market,
    )
    return FakeMarketDataSources().serving(
        FakeMarketDataSources.ports(venue.market_data_venue, history=klines)
    )


def test_fresh_stored_candles_give_an_atr() -> None:
    sources = _sources()
    reading = DailyAtrReader(lambda: sources).read(
        VENUE, SYMBOL, T0 + timedelta(days=_DAYS)
    )

    assert reading.value is not None and reading.value > 0
    assert reading.unavailable == "" and len(reading.candles) == _DAYS
    assert sources.asked == [VENUE.market_data_venue], (
        "the venue's own market (BUG-172)"
    )


@pytest.mark.parametrize(
    ("days", "words"),
    [(0, "no daily candles are stored"), (10, "needs 15")],
    ids=["none", "too-few"],
)
def test_missing_candles_give_no_atr_and_say_why(days: int, words: str) -> None:
    sources = _sources(days)

    reading = DailyAtrReader(lambda: sources).read(
        VENUE, SYMBOL, T0 + timedelta(days=days)
    )

    assert reading.value is None and words in reading.unavailable


def test_candles_that_stopped_arriving_give_no_atr() -> None:
    sources = _sources()
    newest_opens = T0 + timedelta(days=_DAYS - 1)
    fresh = DailyAtrReader(lambda: sources).read(
        VENUE, SYMBOL, newest_opens + MAX_DAILY_CANDLE_AGE
    )
    stale = DailyAtrReader(lambda: sources).read(
        VENUE, SYMBOL, newest_opens + MAX_DAILY_CANDLE_AGE + timedelta(seconds=1)
    )

    assert fresh.value is not None, "two days old is the last that is accepted"
    assert stale.value is None and "more than 2 days ago" in stale.unavailable


def _start_reads(sources: FakeMarketDataSources, at_day: int) -> FuturesStartReads:
    """The reads of a bot on the world's venue (Spot testnet), the clock at `at_day`."""
    contexts: list[GridRunContext] = []

    def capture(context: GridRunContext) -> None:
        contexts.append(context)

    world = grid_world(risk_watch=capture)  # type: ignore[arg-type]  # a context taker, no watch
    world.clock.advance(T0 + timedelta(days=at_day) - world.clock.now())
    return FuturesStartReads(
        contexts[0],
        None,  # type: ignore[arg-type]  # only the ATR is read here
        None,  # type: ignore[arg-type]
        FuturesGridThresholds(),
        DailyAtrReader(lambda: sources),
    )


def test_the_start_reads_the_atr_the_plan_reads(
    caplog: pytest.LogCaptureFixture,
) -> None:
    sources = _sources(venue=SPOT, market=MarketType.SPOT)
    caplog.set_level(logging.INFO, logger="App.Bots.GridExecutor")

    reading = _start_reads(sources, _DAYS).daily_atr_reading()

    planner = DailyAtrReader(lambda: sources).read(
        SPOT, SYMBOL, T0 + timedelta(days=_DAYS)
    )
    assert reading.value is not None and reading.value == planner.value
    assert "larger of" in caplog.text and "[plan-risk]" in caplog.text


def test_the_start_falls_back_to_the_flat_floor_and_says_so(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="App.Bots.GridExecutor")

    reading = _start_reads(_sources(0, SPOT, MarketType.SPOT), 0).daily_atr_reading()

    assert reading.value is None
    assert "flat 0.01 of the exit" in caplog.text
    assert "no daily candles are stored" in caplog.text


def test_unreadable_candles_fall_back_too_never_raise(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO, logger="App.Bots.GridExecutor")
    unregistered = FakeMarketDataSources()  # asking it for a venue raises

    reading = _start_reads(unregistered, 0).daily_atr_reading()

    assert reading.value is None and "could not be read" in reading.unavailable
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1 and warnings[0].exc_info, (
        "a broken store is a WARNING with its traceback"
    )
