"""Candle builders for `IMarketDataRepository`'s contract suite.

A factory is not a test and not a policy, so it does not share a file with
either (`architecture-rule.md` §5 rule 1, and rule 6's own words: "a fixture,
a factory function and the test that uses them are three abstraction levels
the moment any one of them could change without the others needing to").

Published rather than private to the suite: a consumer writing its own test
against `FakeMarketDataRepository` needs candles of exactly this shape, and
the alternative is thirteen keyword arguments at every call site.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: The cadence every builder here defaults to, and the origin every
#: `minutes=` offset is measured from.
MINUTE = TimeFrame.ONE_MINUTE
T0 = datetime(2024, 1, 1, 0, 0, tzinfo=UTC)


def candle(
    symbol: str = "BTCUSDT",
    minutes: int = 0,
    *,
    interval: TimeFrame = MINUTE,
    close_price: float = 105.0,
    closed: bool = True,
) -> MarketData:
    """One candle at `T0 + minutes`, with a `close_time` one cadence later.

    `closed=False` leaves `close_time` in the far future, which is how a
    consumer exercises `unclosed_candles`.
    """
    open_time = T0 + timedelta(minutes=minutes)
    cadence = timedelta(seconds=interval.to_seconds())
    return MarketData(
        symbol=symbol,
        interval=interval.value,
        open_time=open_time,
        open_price=100.0,
        high_price=110.0,
        low_price=90.0,
        close_price=close_price,
        volume=1000.0,
        close_time=open_time + (cadence if closed else timedelta(days=365)),
        quote_asset_volume=105000.0,
        number_of_trades=50,
        taker_buy_base_asset_volume=500.0,
        taker_buy_quote_asset_volume=52500.0,
    )


def at(minutes: int) -> datetime:
    """`T0 + minutes` — the open time `candle(minutes=...)` carries."""
    return T0 + timedelta(minutes=minutes)
