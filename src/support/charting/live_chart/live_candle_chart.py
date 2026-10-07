"""`EPIC-029` ADR D15 — one `ChartCard` loaded and kept live: what a desk's
chart and a bot's chart share.

@details It shows one symbol at one timeframe, reads its stored history
through `LiveChartCoordinator`, and, once `go_live()`, syncs and streams
under the chart's own owner. A subclass decides where live candles come
from (it calls `apply_candle` on the Qt thread) and adds what it draws over
the candles through three hooks: `_on_symbol_shown`, `_on_history_drawn`,
`_on_candle_drawn`. The desk adds its fills, its armed strategy's lines and
its last price (`DeskChart`); the bot adds its overlay (`BotChart`).

Opening a chart reads local history only; `go_live` asks for the stream
(`BUG-107`: opening a screen is not a request to go on the network). The
history arrives through a Qt signal, so the chart widget is touched only on
the Qt thread (`BUG-031`).
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    timeframe_or_fallback,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_callbacks import (
    LiveChartCallbacks,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_coordinator import (
    LiveChartCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.LiveCandleChart")


class LiveCandleChart(QObject):
    """@brief One `ChartCard`, its history and its live candles."""

    #: A line for the owner's log.
    logged = Signal(str)

    _history = Signal(str, list, list, list)
    #: A first window's load settled (drawn, empty or failed), from the
    #: coordinator's worker thread, with the token it was asked with.
    _load_settled = Signal(object)

    def __init__(
        self, chart: ChartCard, ports: LiveChartPorts, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._chart = chart
        self._symbol = ""
        self._interval = self._opening_interval(chart, ports)
        self._live = False
        self._token = CancellationToken()
        #: A first window was asked for and has not settled yet.
        self._pending = False
        self._coordinator = LiveChartCoordinator(
            ports.thread_manager,
            ports.feed,
            LiveChartCallbacks(
                history_ready=self._history.emit,
                load_finished=self._load_settled.emit,
                stream_started=self.logged.emit,
                stream_failed=lambda text: self.logged.emit(f"[ERROR] {text}"),
                log=self.logged.emit,
            ),
            ports.stream_owner,
        )
        self._history.connect(self._on_history)
        self._load_settled.connect(self._on_load_settled)
        chart.toolbar.set_active(self._interval)
        chart.toolbar.sig_timeframe_changed.connect(self._on_timeframe_changed)

    @staticmethod
    def _opening_interval(chart: ChartCard, ports: LiveChartPorts) -> str:
        """The timeframe to open on: `ports.interval`, or the nearest one the
        chart's market can load. The toolbar is told the market first, so its
        bar offers only what the market loads."""
        if ports.market is None:
            return ports.interval
        chart.toolbar.set_market(ports.market)
        interval = timeframe_or_fallback(ports.market, ports.interval)
        if interval != ports.interval:
            logger.info(
                "[live-chart] opening timeframe %s is not offered on %s; using %s",
                ports.interval,
                ports.market.value,
                interval,
            )
        return interval

    @property
    def shown_symbol(self) -> str:
        return self._symbol

    @property
    def shown_interval(self) -> str:
        return self._interval

    @property
    def is_live(self) -> bool:
        return self._live

    def show_symbol(self, symbol: str) -> None:
        """Loads `symbol`'s history, live if the chart already went live."""
        if symbol == self._symbol:
            return
        self._symbol = symbol
        self._chart.set_symbol_title(symbol)
        self._on_symbol_shown(symbol)
        self._restart()

    def go_live(self) -> None:
        """Asks for the live stream, once.

        Before a symbol is shown it only marks the chart live, and the first
        `show_symbol` starts live: restarting here would sync and stream the
        empty symbol, a request nobody made (the re-review of PR 308)."""
        if self._live:
            return
        self._live = True
        if self._symbol:
            self._restart()

    def show_newest_window(self) -> None:
        """Draws the shown symbol's newest first window again at the shown
        timeframe, live if the chart is (`EPIC-033T`): the way back from
        whatever an owner drew in its place."""
        if self._symbol:
            self._restart()

    def shutdown(self) -> None:
        """Cancels the load in flight; the stream is left as it is."""
        self._token.cancel()

    def release_stream(self) -> None:
        """Releases this chart's own stream (`BOT-126`), if it holds one."""
        self._coordinator.stop()

    def _go_quiet(self) -> None:
        """Releases the stream if the chart went live, and is quiet again: a
        symbol shown afterwards reads history only, and `go_live` may ask
        for the stream anew (the PR 321 review)."""
        if self._live:
            self.release_stream()
            self._live = False

    def apply_candle(self, candle: MarketData) -> None:
        """@brief Draws one live candle of the shown symbol and timeframe,
        closing a bar or updating the forming one. Call on the Qt thread."""
        if candle.symbol != self._symbol or candle.interval != self._interval:
            return
        t = candle.close_time.timestamp()
        o, h, low, c = (
            float(candle.open_price),
            float(candle.high_price),
            float(candle.low_price),
            float(candle.close_price),
        )
        bullish = c >= o
        if candle.is_closed:
            self._chart.append_closed_candle(t, o, h, low, c)
            self._chart.append_closed_volume(t, float(candle.volume), bullish)
        else:
            self._chart.update_last_candle(t, o, h, low, c)
            self._chart.update_last_volume(t, float(candle.volume), bullish)
        self._on_candle_drawn(candle)

    def draw_history(self, klines: Sequence[MarketData]) -> None:
        """@brief Draws `klines`, oldest first, as the chart's whole history."""
        rows = list(klines)
        self._render_history(map_klines(rows), map_volume(rows), rows)

    def _on_symbol_shown(self, symbol: str) -> None:
        """Hook: `symbol` became the shown symbol, before its history loads."""

    def _on_history_drawn(self, klines: Sequence[MarketData]) -> None:
        """Hook: the shown symbol's history was drawn."""

    def _on_candle_drawn(self, candle: MarketData) -> None:
        """Hook: a live candle of the shown symbol was drawn."""

    def _on_first_window_requested(self) -> None:
        """Hook: a first window (a new symbol, timeframe or go-live) was asked
        for; until it settles, what is drawn is about to be replaced."""

    def _on_first_window_settled(self) -> None:
        """Hook, on the Qt thread: one first window asked for settled, drawn
        or not (no stored candles, a failed sync). Exactly once per request."""

    def _restart(self) -> None:
        # The load this cancels reports nothing any more (`BUG-150`), so it
        # settles here, on the Qt thread: once per request still holds.
        if self._pending:
            self._pending = False
            self._on_first_window_settled()
        self._pending = True
        self._on_first_window_requested()
        self._token.cancel()
        self._token = CancellationToken()
        if self._live:
            self._coordinator.stop()
        self._coordinator.start(
            self._symbol, self._interval, self._token, go_live=self._live
        )

    def _on_load_settled(self, token: object) -> None:
        # A settle already on its way when its request was replaced belongs
        # to that request, which `_restart` settled.
        if token is self._token and self._pending:
            self._pending = False
            self._on_first_window_settled()

    def _on_timeframe_changed(self, timeframe: str) -> None:
        if timeframe != self._interval:
            self._interval = timeframe
            if self._symbol:
                self._restart()

    def _on_history(
        self, symbol: str, candles: list, volume: list, klines: list
    ) -> None:
        # The coordinator mapped the rows on its worker thread; they are
        # drawn as they came (the PR 321 review). A window of a timeframe the
        # chart has since left is not drawn: its bars would be the wrong width
        # (the review of PR #366).
        if symbol != self._symbol:
            return
        if klines and klines[0].interval != self._interval:
            return
        self._render_history(candles, volume, klines)

    def _render_history(
        self, candles: list, volume: list, klines: Sequence[MarketData]
    ) -> None:
        self._chart.render_historical_data(candles)
        self._chart.render_historical_volume(volume)
        self._on_history_drawn(klines)
