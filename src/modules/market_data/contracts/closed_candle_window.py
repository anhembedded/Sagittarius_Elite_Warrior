"""`EPIC-047H` — a window of closed candles from the host's candle store, as the bridge hands it to the desktop.

@details The VPS tab opens no connection to Binance (decision record 2026-10-27, D1), so the chart's closed
candles are read from the candle store the host already keeps (SQLite, WAL: a second process reads it
while the host writes, assumption A9) and put on the wire. The window is the newest `limit` candles older than
`before`, oldest first, so a chart asks again with `before` set to its oldest to page back.

@par What the window says about itself
`shard_found` is false when the host has no store for the symbol on that venue (nothing was ever fetched
for it): the tab says "not published by the host", and an empty window with `shard_found` true means the
store holds nothing of that timeframe. `older_available` says whether an older candle exists, so the chart
knows whether paging back can return anything.

@par Extension cases
  · another stored series (funding history) - one more window type beside this one, the reader is the same file.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

#: The wire name of a window.
CANDLE_WINDOW_ROOT = "sew.candle-window/1"
#: The most candles one window carries: a chart's own fetch limit is far below it.
MAX_WINDOW_CANDLES = 1500


@dataclass(frozen=True, slots=True)
class StoredCandle:
    """One closed candle of the store, exact: prices cross the wire as decimals, never as floats."""

    open_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal


@dataclass(frozen=True, slots=True)
class CandleWindow:
    venue: TradingVenue
    symbol: str
    timeframe: str
    #: Oldest first.
    candles: tuple[StoredCandle, ...]
    shard_found: bool
    older_available: bool
