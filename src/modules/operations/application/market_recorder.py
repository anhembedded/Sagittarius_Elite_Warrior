"""`EPIC-047H` — the host remembers the last price and the forming candles of the symbols it already streams, for the market-data file.

@details **It opens no connection.** The recorder is a listener on the bus: it hears the `MarketTickEvent`s the
host's bot price streams already publish (`BotPriceWatch` holds one 1m kline stream per bot not at rest), and
it asks the mark board (`IMarkBoard`) for the mark price the exit watches already read each beat. A test
fails if it builds an exchange client (`test_the_recorder_opens_no_connection`). It never touches a lease,
a limit or a key.

**It never delays a tick.** `on_tick` runs on the stream's thread, ahead or behind the bots' own handler of
the same event, so it only stores: a few comparisons and one lock held for no longer than that. Reading
(`snapshot`) is the file writer's, on its own thread. A tick it cannot understand is dropped; this handler
never raises into the bus.

**A symbol's data ages in the open.** The last price carries the moment the host received it, so a stream
that stopped (the bot stopped) leaves a price whose age grows and which the reader never shows as live. A
symbol silent for `FORGET_AFTER` is dropped so the file does not grow without bound.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.application.candle_fold import (
    CandleFold,
    MinuteTick,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_market_snapshots import (
    IMarketSnapshots,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_operations_clock import (
    IOperationsClock,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    SymbolMarket,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_mark_board import (
    IMarkBoard,
    RecordedMark,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.market_data_venue import (
    MarketDataVenue,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

logger = logging.getLogger("App.Operations.MarketRecorder")

#: The interval of the stream the host holds; a tick of another interval is not folded.
STREAM_INTERVAL = TimeFrame.ONE_MINUTE.value
#: A symbol with no tick for this long is dropped from the file.
FORGET_AFTER = timedelta(hours=24)

type Key = tuple[MarketDataVenue, MarketType, str]


@dataclass(slots=True)
class _Watched:
    last_price: Decimal
    last_at: datetime
    folds: dict[TimeFrame, CandleFold] = field(default_factory=dict)


class MarketRecorder(IMarketSnapshots):
    def __init__(
        self,
        timeframes: Sequence[TimeFrame],
        enabled_venues: Callable[[], Sequence[TradingVenue]],
        marks: IMarkBoard,
        clock: IOperationsClock,
    ) -> None:
        self._timeframes = tuple(timeframes)
        self._enabled_venues = enabled_venues
        self._marks = marks
        self._clock = clock
        self._lock = threading.Lock()
        self._watched: dict[Key, _Watched] = {}

    def on_tick(self, event: MarketTickEvent) -> None:
        """Hear one kline update. Never raises, never blocks on anything but its own lock."""
        candle = event.market_data
        if candle.interval != STREAM_INTERVAL:
            return
        try:
            tick = MinuteTick(
                candle.open_time,
                Decimal(str(candle.open_price)),
                Decimal(str(candle.high_price)),
                Decimal(str(candle.low_price)),
                Decimal(str(candle.close_price)),
                Decimal(str(candle.volume)),
            )
        except ArithmeticError:
            logger.debug("A tick of %s was not understood; dropped", candle.symbol)
            return
        key = (event.market_data_venue, event.market_type, candle.symbol)
        now = self._clock.now()
        with self._lock:
            watched = self._watched.get(key)
            if watched is None:
                watched = self._watched[key] = _Watched(tick.close_price, now)
                watched.folds = {tf: CandleFold(tf) for tf in self._timeframes}
            watched.last_price, watched.last_at = tick.close_price, now
            for fold in watched.folds.values():
                fold.add(tick)

    def snapshot(self) -> tuple[SymbolMarket, ...]:
        """The live part of every symbol the host watches, by venue then symbol."""
        now = self._clock.now()
        with self._lock:
            self._watched = {
                key: watched
                for key, watched in self._watched.items()
                if now - watched.last_at < FORGET_AFTER
            }
            held = {
                key: (
                    w.last_price,
                    w.last_at,
                    tuple(f.candle() for f in w.folds.values()),
                )
                for key, w in self._watched.items()
            }
        marks = {(m.venue, m.symbol): m for m in self._marks.latest()}
        rows: dict[tuple[TradingVenue, str], SymbolMarket] = {}
        for venue in self._enabled_venues():
            for (data_venue, market, symbol), (price, at, candles) in held.items():
                if (
                    venue.market_data_venue is data_venue
                    and venue.market_type is market
                ):
                    rows[(venue, symbol)] = SymbolMarket(
                        venue,
                        symbol,
                        price,
                        at,
                        forming=tuple(c for c in candles if c is not None),
                    )
        return tuple(
            _with_mark(rows.get(key), key, marks.get(key))
            for key in sorted({*rows, *marks}, key=lambda k: (k[0].value, k[1]))
        )


def _with_mark(
    row: SymbolMarket | None, key: tuple[TradingVenue, str], mark: RecordedMark | None
) -> SymbolMarket:
    venue, symbol = key
    base = row or SymbolMarket(venue, symbol)
    if mark is None:
        return base
    return SymbolMarket(
        base.venue,
        base.symbol,
        base.last_price,
        base.last_at,
        mark.mark_price,
        mark.read_at,
        base.forming,
    )
