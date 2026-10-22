"""`BOT-227` - the symbol's daily ATR, read from the stored daily candles for the Plan and the Start.

@details The planner's advice always read the stored daily candles (`GetPlannerMarketQuery`); the
Start did not, so the stop-to-liquidation floor could only ever be the flat share at Start. This is
the one reader both call, so a plan and its start judge the floor on one estimate.

It never fetches: the candles are what the app stored. An ATR is not offered when the candles are
too few for it, or when the newest stored candle is older than `MAX_DAILY_CANDLE_AGE`, because an
ATR from candles that stopped arriving describes a market that has since moved. Either way the
reading says why in `unavailable`, and the floor falls back to the owner's flat share and names
that reason (`futures_liq_gap_floor`).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import market_of
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_kind import (
    GRID_MARKETS,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicators.volatility import (
    ATR_DEFAULT_PERIOD,
    HighLowClose,
    atr,
)

#: Enough daily candles for ATR(14) and Bollinger(20) with room to spare.
DAILY_CANDLES = 60
#: The newest stored daily candle must have opened within this long, which is today's or
#: yesterday's: an ATR from older candles is not offered.
MAX_DAILY_CANDLE_AGE = timedelta(days=2)


@dataclass(frozen=True, slots=True)
class DailyAtr:
    """The stored daily candles of a symbol and the ATR they give, or why there is none."""

    #: Oldest first. Kept whole, because the planner's range suggestions read them too.
    candles: tuple[HighLowClose, ...]
    value: Decimal | None
    #: Why `value` is `None`; empty when there is a value.
    unavailable: str = ""


class DailyAtrReader:
    """Reads a symbol's daily ATR from the stored candles."""

    def __init__(self, sources: Callable[[], IMarketDataSources]) -> None:
        """@param sources Resolved when first read, so a host without a candle store boots.
        The candles are the venue's own market's (`BUG-172`), never the default venue's."""
        self._sources = sources

    def read(self, venue: TradingVenue, symbol: str, now: datetime) -> DailyAtr:
        stored = (
            self._sources()
            .ports_for(venue.market_data_venue)
            .history.load(
                market_of(venue, GRID_MARKETS),
                symbol,
                TimeFrame.ONE_DAY,
                limit=DAILY_CANDLES,
                newest_first=True,
            )[::-1]
        )
        candles = tuple(_high_low_close(candle) for candle in stored)
        if not stored:
            return DailyAtr(candles, None, f"no daily candles are stored for {symbol}")
        if len(candles) <= ATR_DEFAULT_PERIOD:
            return DailyAtr(
                candles,
                None,
                f"{len(candles)} daily candles are stored for {symbol}, "
                f"an ATR({ATR_DEFAULT_PERIOD}) needs {ATR_DEFAULT_PERIOD + 1}",
            )
        newest = _aware(stored[-1].open_time)
        if now - newest > MAX_DAILY_CANDLE_AGE:
            return DailyAtr(
                candles,
                None,
                f"the newest stored daily candle of {symbol} opened {newest:%Y-%m-%d %H:%M} UTC, "
                f"more than {MAX_DAILY_CANDLE_AGE.days} days ago",
            )
        return DailyAtr(candles, atr(candles))


def _high_low_close(candle: MarketData) -> HighLowClose:
    return HighLowClose(
        high=Decimal(str(candle.high_price)),
        low=Decimal(str(candle.low_price)),
        close=Decimal(str(candle.close_price)),
    )


def _aware(moment: datetime) -> datetime:
    return moment if moment.tzinfo is not None else moment.replace(tzinfo=UTC)
