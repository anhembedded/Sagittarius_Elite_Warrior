"""`EPIC-029G` — the bots module's one listener to market_data's ticks.

@details A running bot's chart draws live candles, and the ticks reach it on
the Qt thread. trading's screens hear them through market_data's
`MarketTickFeed`, which a module outside market_data reaches only through
`allowlist_module_boundaries.txt`, a list that may only shrink. The bots
module therefore listens to the published event itself, here, once, through
`BaseFeed` (the bridge to the Qt thread), and every bot chart connects to
this Feed's signal rather than subscribing on its own
(`test_one_event_is_not_subscribed_by_two_presenters`).

One market per Feed, as `MarketTickFeed`: Spot and Futures candles share one
bus, and `BTCUSDT@1m` exists on both at two prices.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.base_feed import BaseFeed
from sagittarius_engine.interfaces.i_event_bus import IEventBus


class BotTickFeed(BaseFeed):
    """@brief Re-emits, on the Qt thread, each candle of one market."""

    #: Carries the tick's `MarketData`.
    candle = Signal(object)

    def __init__(
        self, event_bus: IEventBus, market: MarketType, parent: QObject | None = None
    ) -> None:
        # Set before `super().__init__`: `BaseFeed.__init__` subscribes.
        self._market = market
        super().__init__(event_bus, parent)

    def _subscribe(self) -> None:
        self._events.on(MarketTickEvent, self._forward)

    def _forward(self, event: MarketTickEvent) -> None:
        if event.market_type is self._market:
            self.candle.emit(event.market_data)
