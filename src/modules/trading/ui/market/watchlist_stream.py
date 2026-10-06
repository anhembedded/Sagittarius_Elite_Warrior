"""The Market mode's Watchlist stream: one `IMarketStream` owner, started when
the mode goes live, released when another mode takes the window (`BOT-165`)
and when the screen closes. Only this owner is ever stopped here; a chart, a
bot or an armed strategy streaming the same symbol holds its own."""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame

from .market_dependencies import MarketDependencies
from .market_metadata_precisions import MarketMetadataPrecisions
from .market_view import MarketView
from .watchlist_filters import WatchlistFilters

logger = logging.getLogger("App.Trading.Market")

#: The Watchlist's own owner on `IMarketStream`; each chart has its own
#: (`market_chart.stream_owner_for`).
WATCHLIST_STREAM_OWNER = "market.watchlist"
#: The Watchlist's candles: a row's change is its minute's change.
WATCHLIST_INTERVAL = TimeFrame.ONE_MINUTE
_PAUSED = "Market data: paused while another mode shows."


class WatchlistStream:
    """@brief Starts and releases the Watchlist's stream for the chosen market."""

    def __init__(
        self,
        view: MarketView,
        deps: MarketDependencies,
        market: Callable[[], MarketType],
    ) -> None:
        self._view = view
        self._deps = deps
        self._market = market
        self._running = False
        self._filters = self._watchlist_filters()

    @property
    def running(self) -> bool:
        return self._running

    def _watchlist_filters(self) -> WatchlistFilters | None:
        """The Watchlist writes prices and volumes in the chosen market's
        tick and step sizes, read once it goes live (`EPIC-033N`)."""
        deps = self._deps
        if deps.filters is None:
            return None
        watchlist = self._view.watchlist
        watchlist.use_precisions(
            MarketMetadataPrecisions(deps.filters.cache, self._market)
        )
        filters = WatchlistFilters(deps.filters.provider, deps.thread_manager)
        filters.fetched.connect(watchlist.refresh_precisions)
        return filters

    def start(self) -> None:
        """Streams the chosen market's symbols; a second start replaces the
        first (`IMarketStream.start`), so a new market needs no stop."""
        symbols = list(self._deps.symbols)
        self._running = True
        outcome = self._deps.stream.start(
            WATCHLIST_STREAM_OWNER, self._market(), symbols, WATCHLIST_INTERVAL
        )
        if outcome.success:
            if self._filters is not None:
                self._filters.fetch(self._market(), self._deps.symbols)
            self._view.set_stream_text("Market data: live")
            self._view.log.append(f"Live for {', '.join(symbols)}.")
            return
        # SPEC-002 §4/§5: a stream that did not start says so, or it reads
        # as "no tick yet".
        logger.warning(
            "[market] watchlist stream did not start for %s: %s",
            symbols,
            outcome.message,
        )
        self._view.set_stream_text("Market data: failed to start")
        self._view.log.append(f"Failed to start stream: {outcome.message}", "error")

    def pause(self) -> None:
        """Another mode took the window: release the Watchlist's owner."""
        if not self._running:
            return
        self.release()
        self._view.set_stream_text(_PAUSED)
        logger.info("[market] watchlist stream released: mode hidden")

    def release(self) -> None:
        self._running = False
        self._deps.stream.stop(WATCHLIST_STREAM_OWNER)

    def drop_filters(self) -> None:
        if self._filters is not None:
            self._filters.drop()
