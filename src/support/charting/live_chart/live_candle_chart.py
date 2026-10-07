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
from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_timeframes import (
    timeframe_or_fallback,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.chart_failure_notice import (
    ChartFailureChannel,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_callbacks import (
    LiveChartCallbacks,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_coordinator import (
    LiveChartCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_fsm_matrix import (
    COMMAND_EVENT,
    STATE_COMMAND,
    LiveChartCommand,
    LiveChartEvent,
    LiveChartState,
    next_state,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_state_chip import (
    LiveStateChip,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.LiveCandleChart")


class LiveCandleChart(QObject):
    """@brief One `ChartCard`, its history and its live candles."""

    #: A line for the owner's log.
    logged = Signal(str)
    #: The chart's live state changed (`LiveChartState`).
    liveStateChanged = Signal(object)

    _history = Signal(str, list, list, list)
    #: A first window's load settled (drawn, empty or failed), from the
    #: coordinator's worker thread, with the token it was asked with.
    _load_settled = Signal(object)
    #: The coordinator's stream reports, from its worker thread.
    #: Each carries the token of the request it reports on.
    _stream_opened = Signal(object, str)
    #: `(token, headline, detail)` of a failed sync or stream (`BOT-169`).
    _stream_lost = Signal(object, str, str)
    #: `(token, headline, detail)`: the history could not be loaded, at rest.
    _load_lost = Signal(object, str, str)

    def __init__(
        self, chart: ChartCard, ports: LiveChartPorts, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._chart = chart
        self._symbol = ""
        self._interval = self._opening_interval(chart, ports)
        self._live = False
        self._failures = ChartFailureChannel.of(ports, self.logged.emit)
        self._clock: Callable[[], float] = ports.clock
        self._state = LiveChartState.HISTORY
        self._syncing_stream_action = False
        self._error = ""
        self._last_update: float | None = None
        self._token = CancellationToken()
        #: A first window was asked for and has not settled yet.
        self._pending = False
        self._coordinator = LiveChartCoordinator(
            ports.thread_manager,
            ports.feed,
            LiveChartCallbacks(
                history_ready=self._history.emit,
                load_finished=self._load_settled.emit,
                stream_started=self._stream_opened.emit,
                stream_failed=self._stream_lost.emit,
                load_failed=self._load_lost.emit,
                log=self.logged.emit,
            ),
            ports.stream_owner,
        )
        self._history.connect(self._on_history)
        self._load_settled.connect(self._on_load_settled)
        self._stream_opened.connect(self._on_stream_opened)
        self._stream_lost.connect(self._on_stream_lost)
        self._load_lost.connect(self._on_load_lost)
        self.live_stream_action = self._stream_action()
        self._chip = LiveStateChip(self.last_update_age)
        self._chip.commandRequested.connect(self.run_command)
        if ports.live_commands:
            chart.add_to_header(self._chip)
            chart.plot_layout.main_plot.vb.menu.addAction(self._chip.command)
        chart.toolbar.set_active(self._interval)
        chart.toolbar.sig_timeframe_changed.connect(self._on_timeframe_changed)

    def _stream_action(self) -> QAction:
        """The mode's Live stream menu command, checked while the chart
        connects or is live (`live_stream_command.py`)."""
        action = QAction("&Live stream", self)
        action.setCheckable(True)
        action.toggled.connect(self._on_stream_toggled)
        return action

    def _on_stream_toggled(self, checked: bool) -> None:
        if self._syncing_stream_action or checked == self._streaming:
            return
        self.run_command(STATE_COMMAND[self._state])

    @property
    def _streaming(self) -> bool:
        return self._state in (LiveChartState.CONNECTING, LiveChartState.LIVE)

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

    @property
    def live_state(self) -> LiveChartState:
        """Whether the chart is showing history, connecting, live or failed
        (`EPIC-034G`): the coordinator's own lifecycle, seen from here."""
        return self._state

    @property
    def live_error(self) -> str:
        """Why the stream failed; empty unless the state is `ERROR`."""
        return self._error

    def last_update_age(self) -> float | None:
        """Seconds since the last live candle was drawn; `None` before one."""
        if self._last_update is None:
            return None
        return self._clock() - self._last_update

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
        self.run_command(LiveChartCommand.GO_LIVE)

    def run_command(self, command: LiveChartCommand) -> None:
        """What the chip's button and the chart's menu ask: Go live, Cancel,
        Stop live or Retry. A command the state does not offer is dropped, so
        a second Go live changes nothing."""
        if not self._dispatch(COMMAND_EVENT[command]):
            return
        if command in (LiveChartCommand.GO_LIVE, LiveChartCommand.RETRY):
            self._live = True
        else:
            self._release_live()
        if self._symbol:
            self._restart()

    def show_newest_window(self) -> None:
        """Draws the shown symbol's newest first window again at the shown
        timeframe, live if the chart is (`EPIC-033T`): the way back from
        whatever an owner drew in its place."""
        if self._symbol:
            self._restart()

    def shutdown(self) -> None:
        """Cancels the load in flight; the stream is left as it is. A failure
        bar of this chart goes with it: its Retry would target a closed chart."""
        self._token.cancel()
        self._failures.clear()

    def release_stream(self) -> None:
        """Releases this chart's own stream (`BOT-126`), if it holds one."""
        self._coordinator.stop()

    def _go_quiet(self) -> None:
        """The owner closed the chart: its stream is released and its state
        is History again (the PR 321 review)."""
        self._release_live()
        self._dispatch(LiveChartEvent.SHUT_DOWN)

    def _release_live(self) -> None:
        """Releases the stream if the chart went live, and is quiet again: a
        symbol shown afterwards reads history only, and `go_live` may ask
        for the stream anew."""
        if self._live:
            self.release_stream()
            self._live = False

    def apply_candle(self, candle: MarketData) -> None:
        """@brief Draws one live candle of the shown symbol and timeframe,
        closing a bar or updating the forming one. Call on the Qt thread."""
        if candle.symbol != self._symbol or candle.interval != self._interval:
            return
        self._last_update = self._clock()
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
        # settles here, on the Qt thread: once per request still holds. A new
        # request supersedes the notice of the last one (`BUG-172`).
        self._failures.clear()
        if self._pending:
            self._pending = False
            self._on_first_window_settled()
        self._pending = True
        self._on_first_window_requested()
        self._token.cancel()
        self._token = CancellationToken()
        self._last_update = None
        if self._live:
            self._dispatch(LiveChartEvent.LOAD_RESTARTED)
            self._coordinator.stop()
        self._coordinator.start(
            self._symbol, self._interval, self._token, go_live=self._live
        )

    def _dispatch(self, event: LiveChartEvent, reason: str = "") -> bool:
        """Moves the live state by `event`; `False` when the table declares
        no move from here, so a report already on its way when the user
        cancelled moves nothing."""
        target = next_state(self._state, event)
        if target is None:
            logger.debug(
                "[live-chart] %s dropped in %s (%s)",
                event.value,
                self._state.value,
                self._symbol,
            )
            return False
        logger.info(
            "[live-chart] %s: %s -> %s on %s",
            self._symbol or "-",
            self._state.value,
            target.value,
            event.value,
        )
        self._error = reason if target is LiveChartState.ERROR else ""
        if target is not LiveChartState.ERROR:
            self._failures.clear()
        self._state = target
        self._syncing_stream_action = True
        self.live_stream_action.setChecked(self._streaming)
        self._syncing_stream_action = False
        self._chip.show_state(target, self._error)
        self.liveStateChanged.emit(target)
        return True

    def _on_stream_opened(self, token: object, text: str) -> None:
        # A report of a request since replaced (a new symbol, a Retry) says
        # nothing about the one now asked for.
        if token is self._token and self._dispatch(LiveChartEvent.STREAM_STARTED):
            self.logged.emit(text)
            self._failures.clear()

    def _on_stream_lost(self, token: object, headline: str, detail: str) -> None:
        if token is not self._token or not self._dispatch(
            LiveChartEvent.STREAM_FAILED, headline
        ):
            return
        self._failures.tell(
            headline, detail, lambda: self.run_command(LiveChartCommand.RETRY)
        )

    def _on_load_lost(self, token: object, headline: str, detail: str) -> None:
        """`BUG-172`: the history of a chart at rest could not be fetched or does
        not exist. Said in words with a Retry that loads it again; the live state is
        untouched, so the Retry opens no stream."""
        if token is self._token:
            self._failures.tell(headline, detail, self._restart)

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
