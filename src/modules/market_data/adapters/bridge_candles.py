"""`EPIC-047H` — `IBridgeCandles` over the host's candle store, read-only."""

from __future__ import annotations

import re
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.adapters.persistence.readonly_candle_shards import (
    ReadOnlyCandleShards,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.closed_candle_window import (
    CANDLE_WINDOW_ROOT,
    MAX_WINDOW_CANDLES,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    Wired,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.i_bridge_candles import (
    CandleQuery,
    IBridgeCandles,
    UnknownCandleSeriesError,
)

#: What a symbol is (`shard_name` refuses anything else): a shard path is never built from free text.
_SYMBOL = re.compile(r"^[A-Za-z0-9]{1,32}$")


class StoreBridgeCandles(IBridgeCandles):
    def __init__(self, directory: Path) -> None:
        self._shards = ReadOnlyCandleShards(directory)

    def window(self, query: CandleQuery) -> Wired:
        venue = _venue_of(query.venue)
        if _SYMBOL.match(query.symbol) is None:
            raise UnknownCandleSeriesError("a symbol is letters and digits")
        try:
            timeframe = TimeFrame(query.timeframe)
        except ValueError as failure:
            raise UnknownCandleSeriesError(
                f"{query.timeframe[:12]!r} is not a timeframe"
            ) from failure
        if not 1 <= query.limit <= MAX_WINDOW_CANDLES:
            raise UnknownCandleSeriesError(
                f"limit is between 1 and {MAX_WINDOW_CANDLES}"
            )
        window = self._shards.window(
            venue, query.symbol.upper(), timeframe.value, query.limit, query.before
        )
        return Wired(CANDLE_WINDOW_ROOT, window)


def _venue_of(value: str) -> TradingVenue:
    try:
        venue = TradingVenue(value)
    except ValueError as failure:
        raise UnknownCandleSeriesError(f"{value[:24]!r} is not a venue") from failure
    if venue is TradingVenue.DISABLED:
        raise UnknownCandleSeriesError("a disabled venue has no candles")
    return venue
