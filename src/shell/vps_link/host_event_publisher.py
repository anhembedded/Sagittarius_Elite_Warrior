"""`EPIC-047E` — what the host's picture changes become events on the bus, for the Bots screen's own feeds.

@details The Bots screen hears `BotChangedEvent` (a bot was saved or deleted) and `MarketTickEvent` (a candle of a
market) and nothing else from the application. On the VPS tab the bus is a private one, and this is the only thing
that publishes to it, from the link's thread; the screen's feeds (`BotChangesFeed`, `BotTickFeed`) bring the events to
the Qt thread as they always did. So the screen reads a remote host and a local one the same way (`EPIC-048`).

@par A live candle is only as live as the host's file
A forming candle is published only while the host's market file is live (`FactsState.LIVE`); a quiet host publishes
nothing, so a chart freezes at its last candle instead of drawing an old price as a new one (decision record
2026-10-27, D5). The fields the host does not publish for a forming candle (the quote volume, the trade count, the
taker volumes) are zero and are read by no screen.

@par Extension cases
  · another event the screen learns to hear — one method on `IHostWorldListener` and one emit here.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.market_data_document import (
    FormingCandle,
    MarketDataDocument,
    SymbolMarket,
)
from Sagittarius_Elite_Warrior.src.shell.vps_link.link_host_world import (
    IHostWorldListener,
)
from sagittarius_engine.interfaces.i_event_bus import IEventBus

logger = logging.getLogger("App.VpsTab")
_ZERO = 0.0


class HostEventPublisher(IHostWorldListener):
    def __init__(self, bus: IEventBus) -> None:
        self._bus = bus

    def on_bot_changed(self, bot_id: str, removed: bool) -> None:
        self._bus.emit(BotChangedEvent(bot_id=bot_id, removed=removed))

    def on_file_changed(self, kind: str) -> None:
        """Nothing to publish: no screen of the application hears a host file's liveness on the bus."""

    def on_market(self, market: MarketDataDocument) -> None:
        for symbol in market.symbols:
            for candle in symbol.forming:
                tick = _tick_of(symbol, candle)
                if tick is not None:
                    self._bus.emit(tick)


def _tick_of(symbol: SymbolMarket, candle: FormingCandle) -> MarketTickEvent | None:
    """The tick of one forming candle, or `None` for one this build cannot name (a timeframe or a venue
    it does not know): that candle is skipped and says so at DEBUG, the others still tick."""
    market_type = symbol.venue.market_type
    try:
        span = timedelta(seconds=TimeFrame(candle.timeframe).to_seconds())
    except ValueError:
        span = None
    if market_type is None or span is None:
        logger.debug(
            "[vps-ticks] skipped %s %s on %s: not a market or timeframe this build knows",
            symbol.symbol,
            candle.timeframe,
            symbol.venue.value,
        )
        return None
    data = MarketData(
        symbol=symbol.symbol,
        interval=candle.timeframe,
        open_time=candle.open_time,
        open_price=float(candle.open_price),
        high_price=float(candle.high_price),
        low_price=float(candle.low_price),
        close_price=float(candle.close_price),
        volume=float(candle.volume),
        close_time=candle.open_time + span - timedelta(milliseconds=1),
        quote_asset_volume=_ZERO,
        number_of_trades=0,
        taker_buy_base_asset_volume=_ZERO,
        taker_buy_quote_asset_volume=_ZERO,
        is_closed=False,
    )
    return MarketTickEvent(
        market_data=data,
        market_type=market_type,
        market_data_venue=symbol.venue.market_data_venue,
    )
