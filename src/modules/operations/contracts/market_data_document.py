"""`EPIC-047H` — the market-data file as one value: the live prices and forming candles the host holds for each symbol it watches.

@details The VPS tab opens no connection to Binance (decision record 2026-10-27, D1), so the chart's
live part reaches it from the host: the last price and the forming candle of each timeframe (from the
kline stream the host already holds for every bot not at rest, `BotPriceWatch`) and the mark price
(from the read each exit watch already makes, `IMarkBoard`). The host writes it to
`state/market-data.json` at most once a second; the bridge reads it. Closed candles are not here: they
are read from the host's candle store (`IBridgeCandles`).

@par How a reader tells a stale price from a live one
Each price carries the moment the host *received* it (`last_at`, `mark_at`, the host's clock), and the
file's header says when the host last wrote and how often it promises to (`heartbeat_s`): a symbol whose
stream stopped keeps its last price with its own age, and a reader never shows it as live.

@par A candle folded from the 1m stream
The host streams the 1m kline only (`BotPriceWatch`, `_STREAM_INTERVAL`). A longer timeframe's forming
candle is folded from those ticks; `complete` is false when the host began folding inside the bucket
(it started, or the stream did, after the bucket opened), so its open and its extremes are those since
then and not the bucket's own. The tab shows such a candle as partial, never as complete.

@par Extension cases
  · another timeframe - one more code in `PUBLISHED_TIMEFRAMES`' source, no change here;
  · a second price source (a `bookTicker` mid) - one more optional field of `SymbolMarket`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.host_facts_document import (
    HostFactsHeader,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

MARKET_DATA_FILE_NAME = "market-data.json"
#: The most the host promises to go without writing the file while it lives; a reader calls it quiet after a few.
MARKET_HEARTBEAT_SECONDS = 5
#: Seconds between two looks at the prices. The file is written at most this often (decision record D3).
MARKET_POLL_SECONDS = 1


@dataclass(frozen=True, slots=True)
class FormingCandle:
    """The candle of `timeframe` that is open now, as the host has folded it."""

    timeframe: str
    open_time: datetime
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: Decimal
    #: False when the host began folding inside this bucket, so the open and the extremes are partial.
    complete: bool


@dataclass(frozen=True, slots=True)
class SymbolMarket:
    """What the host holds live about one symbol on one trading venue. A value never received is `None`."""

    venue: TradingVenue
    symbol: str
    last_price: Decimal | None = None
    #: When the host received the last price, on its clock.
    last_at: datetime | None = None
    mark_price: Decimal | None = None
    #: When the host recorded the mark it read (futures venues only).
    mark_at: datetime | None = None
    forming: tuple[FormingCandle, ...] = ()


@dataclass(frozen=True, slots=True)
class MarketDataDocument:
    header: HostFactsHeader
    symbols: tuple[SymbolMarket, ...] = ()
