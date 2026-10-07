"""Which timeframes a market can load — the one place that knows.

@details Binance USD-M Futures serves no 1-second klines
(`fapi/v1/klines?interval=1s` answers `-1120 Invalid interval`; data.binance.vision
lists `1s/` for Spot only), so a picker that offered `1s` on Futures sent the
user to a load or a sync that could never succeed. Every picker asks this rule
instead of keeping its own `if`.

`FUTURES_COIN_M` shares the Futures interval list (Binance's documented kline
intervals start at `1m` there too); it was not probed, and nothing in the app
offers it yet.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

#: What a market cannot load. A market missing here loads every timeframe, so a
#: new `MarketType` member is a decision made here, with its evidence.
_UNSUPPORTED: dict[MarketType, frozenset[TimeFrame]] = {
    MarketType.SPOT: frozenset(),
    MarketType.FUTURES_USD_M: frozenset({TimeFrame.ONE_SECOND}),
    MarketType.FUTURES_COIN_M: frozenset({TimeFrame.ONE_SECOND}),
}


def timeframes_for(market: MarketType) -> tuple[TimeFrame, ...]:
    """The timeframes `market` can load, shortest first."""
    unsupported = _UNSUPPORTED[market]
    return tuple(
        sorted(
            (tf for tf in TimeFrame if tf not in unsupported),
            key=lambda tf: tf.to_seconds(),
        )
    )


def supports_timeframe(market: MarketType, code: str) -> bool:
    """Whether `market` can load the timeframe with exchange code `code`.

    @details A code the domain does not know is simply not supported: codes
    arrive from remembered state on disk, which can name anything.
    """
    return any(tf.value == code for tf in timeframes_for(market))


def timeframe_or_fallback(market: MarketType, code: str) -> str:
    """`code` when `market` loads it, else the shortest supported timeframe
    that is not shorter than it — for `1s` on Futures, `1m`."""
    if supports_timeframe(market, code):
        return code
    supported = timeframes_for(market)
    try:
        wanted = TimeFrame(code).to_seconds()
    except ValueError:
        return supported[0].value
    return next(
        (tf for tf in supported if tf.to_seconds() >= wanted), supported[-1]
    ).value
