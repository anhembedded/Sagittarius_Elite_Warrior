"""`BOT-019` — Watchlist / Market Overview presenter.

Tracks several symbols at once as a table (last price, % change, volume)
instead of requiring a `ChartCard` per symbol — reuses the already-completed
live-stream infrastructure (`IMarketStream`, `MarketTickEvent`/
`MarketTickFeed`) rather than inventing a second one.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_stream import (
    IMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.market_tick_feed import (
    MarketTickFeed,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.app_defaults import (
    default_symbol_options,
)
from sagittarius_engine.extensions.pyside_mvc import BasePresenter

if TYPE_CHECKING:
    from sagittarius_engine.interfaces.i_container import IContainer

    from .watchlist_view import WatchlistView

#: This screen's own floor, unrelated to any other screen's fallback
#: (`app_defaults.py`'s own module docstring: "each function takes the
#: caller's own fallback" — sharing one across screens has silently changed
#: another screen's starting list before).
_FALLBACK_SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "BNBUSDT")

#: `IMarketStream.start()`'s subscription-set owner id for this screen,
#: distinct from Dashboard's/Trading's — releasing it on shutdown never
#: touches another screen's own subscriptions (`IMarketStream`'s own
#: docstring: "Another owner's subscriptions are untouched").
_STREAM_OWNER_ID = "watchlist"

logger = logging.getLogger("App.Watchlist")


class WatchlistPresenter(BasePresenter):
    """@brief Orchestrator Presenter for the Watchlist screen (`BOT-019`)."""

    INITIAL_STATE = None

    def __init__(self, view: WatchlistView, container: IContainer) -> None:
        super().__init__(view, container)
        self._market_stream = container.resolve(IMarketStream)

        symbols = default_symbol_options(self.config.get_all(), _FALLBACK_SYMBOLS)
        self.view.model.set_symbols(symbols)

        # One place hears `MarketTickEvent`, many screens display it
        # (`architecture-rule.md` §6) — this presenter constructs its own
        # `MarketTickFeed` instance, the same pattern Dashboard/Trading
        # already use, rather than calling `event_bus.on(...)` directly.
        self._market_tick_feed = MarketTickFeed(self.event_bus, parent=self)
        self._market_tick_feed.marketTick.connect(self._handle_market_tick)

        outcome = self._market_stream.start(
            _STREAM_OWNER_ID, symbols, TimeFrame.ONE_MINUTE
        )
        if outcome.success:
            self.view.set_status(f"Live for {', '.join(symbols)}.", is_error=False)
        else:
            # `SPEC-002` §4/§5 — a failed start must say so on screen, the
            # same promise Dashboard's `stream_lifecycle_controller.py` and
            # Trading's `chart_coordinator.py` already keep for their own
            # `IMarketStream.start()` call; a silently-unstarted stream
            # would otherwise be indistinguishable from "no tick yet".
            logger.warning(
                "[watchlist] stream did not start for %s: %s",
                symbols,
                outcome.message,
            )
            self.view.set_status(
                f"Failed to start stream: {outcome.message}", is_error=True
            )

    def _handle_market_tick(self, event: MarketTickEvent) -> None:
        market_data = event.market_data
        if market_data.open_price == 0.0:
            logger.warning(
                "[watchlist] %s tick has a zero open_price — skipping the "
                "percent-change computation to avoid dividing by zero",
                market_data.symbol,
            )
            return
        percent_change = (
            (market_data.close_price - market_data.open_price)
            / market_data.open_price
            * 100.0
        )
        self.view.model.update_tick(
            market_data.symbol,
            market_data.close_price,
            percent_change,
            market_data.volume,
        )

    def shutdown(self) -> None:
        """Releases this screen's stream subscription — never another
        screen's, since `_STREAM_OWNER_ID` is this screen's own."""
        self._market_stream.stop(_STREAM_OWNER_ID)
