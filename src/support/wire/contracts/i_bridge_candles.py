"""`EPIC-047H` — the host's closed candles, as the bridge reads them. Implemented by `market_data` (`modules/market_data/link.py`)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.wire.contracts.bridge_values import (
    Wired,
)


@dataclass(frozen=True, slots=True)
class CandleQuery:
    """What a `candles` call asks: the newest `limit` candles of one series older than `before` (`None`: the newest)."""

    #: A `TradingVenue` value (`spot_testnet`, `futures_mainnet`, ...): the chart's venue is a bot's venue.
    venue: str
    symbol: str
    #: A timeframe code (`1m`, `1h`, ...).
    timeframe: str
    limit: int
    before: datetime | None = None


class UnknownCandleSeriesError(ValueError):
    """The query names a venue or a timeframe this build does not know, or a symbol that is not one."""


class IBridgeCandles(ABC):
    @abstractmethod
    def window(self, query: CandleQuery) -> Wired:
        """The window of closed candles the host's store holds, read-only.
        @raise UnknownCandleSeriesError The query is not a series this build can name."""


def candle_venue_code(venue: TradingVenue) -> str:
    """The venue as a `candles` call and a `CandleQuery` name it: a `TradingVenue` value, one spelling for both ends."""
    return venue.value
