"""The Market mode's presenter (`EPIC-033H`, SPEC-002, SPEC-003).

@par What it does
- **Watchlist:** seeds the tracked symbols and updates each row from the
  market's ticks (`MarketTickFeed`, through `market_ticks.py`).
- **Charts:** opens a symbol's chart when the user activates it in the
  Watchlist (or brings it forward when it is open), closes one when its tab
  closes, and forwards each tick to the chart of its symbol. The checked
  indicators apply to every open chart.
- **Going live:** the first time the mode shows, the first tracked symbol's
  chart opens from local history. The stream starts only on the user's own
  open of the mode (`BUG-104`, `BUG-107`): a restore at start says so in the
  status bar and waits; once live, each chart opened later goes live too.
- **View → Spot market or Futures market (`EPIC-033Q`):** the market is the mode's
  state, remembered between runs. Choosing the other one reopens every open
  chart on its candles, blanks the Watchlist and, once live, moves its
  stream; a tick of the other market never reaches either.
- **Tools → Check connection (SPEC-003):** asks the account in the
  background, fenced by an action id (`async-ui-action-rule.md` §1), and
  shows the answer as a word in the status bar; a failure also says what to
  do in a message.

@par What it replaces
The Watchlist screen (`watchlist_presenter.py`, retired here) and, for
watching the market, the Dev Board's chart column; the Developer mode
replaced the rest of the Dev Board, which `EPIC-033P` deleted.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Signal
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.events.market_tick_event import (
    MarketTickEvent,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market_ticks import (
    market_tick_feed,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_catalog import (
    IndicatorScriptCatalog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_presenter import (
    CommandPresenter,
    ICommandBinder,
)
from sagittarius_engine.extensions.pyside_mvc import safe_ui_action
from sagittarius_engine.interfaces.i_container import IContainer

from .chart_history import ChartHistory
from .chart_history_commands import ChartHistoryCommands
from .connection_words import (
    CHECKING,
    NOT_CHECKED,
    connection_word,
    error_text,
    failure_text,
)
from .indicator_params_command import IndicatorParamsCommand
from .market_chart import ChartSources, MarketChart
from .market_choice import MARKET_TEXT, MarketChoice
from .market_commands import CHECK_CONNECTION, CLOSE_CHART
from .market_dependencies import MarketDependencies, market_dependencies_for
from .market_view import IndicatorChoice, MarketView

logger = logging.getLogger("App.Trading.Market")

#: The Watchlist's own owner on `IMarketStream`; each chart has its own
#: (`market_chart.stream_owner_for`).
WATCHLIST_STREAM_OWNER = "market.watchlist"
#: The Watchlist's candles: a row's change is its minute's change.
WATCHLIST_INTERVAL = TimeFrame.ONE_MINUTE
_CHECK = "check_connection"
_NOT_LIVE = "Market data: not live. Choose Market on the mode bar to start."


class MarketPresenter(CommandPresenter):
    """@brief The Watchlist, the charts and the connection check."""

    #: `(action_id, status | None, error | None)`, from the worker thread.
    connectionChecked = Signal(tuple)
    #: Whether Check connection may start: off while one runs.
    checkConnectionEnabled = Signal(bool)
    #: Whether a chart is open for Close chart to close.
    closeChartEnabled = Signal(bool)

    def __init__(
        self,
        view: MarketView,
        container: IContainer,
        dependencies: MarketDependencies,
    ) -> None:
        super().__init__(view, container)
        self.view: MarketView = view
        self._deps = dependencies
        self._charts: dict[str, MarketChart] = {}
        self._indicators: tuple[str, ...] = self._default_indicators()
        self._opened = False
        self._live = False
        self._checks: ActionOwnershipTracker[str, None, None] = ActionOwnershipTracker()
        self.choice = MarketChoice(dependencies.state, self)
        self._history = ChartHistoryCommands(view, lambda: self._charts, self)
        self._params = IndicatorParamsCommand(
            view,
            IndicatorScriptCatalog(dependencies.scripts),
            dependencies.params_store,
            self,
        )
        self._params.edited.connect(self._redraw_indicator)
        view.watchlist.set_symbols(list(dependencies.symbols))
        view.set_indicator_choices(self._indicator_choices())
        view.set_connection_text(NOT_CHECKED)
        view.set_stream_text("Market data: not live")
        self._ticks = market_tick_feed(
            self.event_bus, lambda: self.choice.current, self
        )
        self._ticks.marketTick.connect(self._on_tick)
        view.symbol_opened.connect(self._open_chart)
        view.chart_closed.connect(self._close_chart)
        view.indicators_changed.connect(self._show_indicators)
        self.connectionChecked.connect(self._on_connection_checked)
        self.choice.changed.connect(self._on_market_changed)

    # -- the mode ------------------------------------------------------------

    def bind_commands(self, binder: ICommandBinder) -> None:
        binder.bind(
            CHECK_CONNECTION,
            lambda _checked: self.check_connection(),
            enabled=self.checkConnectionEnabled,
        )
        binder.bind(
            CLOSE_CHART,
            lambda _checked: self._close_chart(self.view.current_symbol),
            enabled=self.closeChartEnabled,
            initially_enabled=bool(self._charts),
        )
        self.choice.bind_commands(binder)
        self._history.bind_commands(binder)
        self._params.bind_commands(binder)

    def on_mode_shown(self, source: NavigationSource) -> None:
        """`IShownAsMode`: the first showing opens a chart from local history;
        the user's own open starts the stream (`BUG-104`)."""
        if not self._opened:
            self._opened = True
            if self._deps.symbols:
                self._open_chart(self._deps.symbols[0])
        if self._live:
            return
        if source is not NavigationSource.USER_INTENT:
            self.view.set_stream_text(_NOT_LIVE)
            return
        self._go_live()

    @property
    def charts(self) -> dict[str, MarketChart]:
        return dict(self._charts)

    def shutdown(self) -> None:
        """Releases this mode's streams — the Watchlist's and each chart's,
        never another mode's (each owner is this mode's own)."""
        self._checks.invalidate_active()
        for chart in self._charts.values():
            chart.shutdown()
            chart.release_stream()
        self._deps.stream.stop(WATCHLIST_STREAM_OWNER)

    # -- View → Spot market, Futures market (`EPIC-033Q`) ----------------------------------

    def _on_market_changed(self, market: MarketType) -> None:
        """Nothing of the previous market stays: its charts close (their loads
        cancelled, their streams released) and reopen in tab order on the new
        market's candles; the Watchlist starts blank and, once live, streams
        the new market."""
        symbols = self.view.open_symbols
        current = self.view.current_symbol
        for symbol in symbols:
            self._close_chart(symbol)
        self.view.watchlist.set_symbols(list(self._deps.symbols))
        if self._live:
            self._start_watchlist_stream()
        for symbol in symbols:
            self._open_chart(symbol)
        if current:
            self.view.show_chart(current)
        self.view.log.append(f"Showing {MARKET_TEXT[market]} candles.")

    # -- Tools → Check connection (SPEC-003) ---------------------------------

    @safe_ui_action
    def check_connection(self) -> None:
        action = self._checks.begin_action(_CHECK, None, None)
        self.checkConnectionEnabled.emit(False)
        self.view.set_connection_text(CHECKING)
        logger.info("[market] connection check %d started", action.action_id)
        self._deps.thread_manager.submit(self._run_check, action.action_id)

    def _run_check(self, action_id: int) -> None:
        """A worker thread: touches no widget, reports through a signal."""
        try:
            status = self._deps.account.check_connection()
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is reported, not lost to a thread's traceback
            self.connectionChecked.emit((action_id, None, str(exc)))
            return
        self.connectionChecked.emit((action_id, status, None))

    def _on_connection_checked(self, payload: tuple) -> None:
        action_id, status, error = payload
        if not self._checks.is_current_pending(action_id, _CHECK):
            self._checks.log_stale_callback("check_connection", action_id, _CHECK)
            return
        self.checkConnectionEnabled.emit(True)
        if isinstance(status, ExchangeConnectionStatus):
            self._checks.finish_action(action_id, ActionOutcome.SUCCEEDED)
            self._show_status(status)
            return
        self._checks.finish_action(action_id, ActionOutcome.FAILED)
        text = error_text(str(error))
        logger.warning("[market] connection check %d failed: %s", action_id, error)
        self.view.set_connection_text("Exchange: not connected")
        self.view.log.append(text, "error")
        self.view.show_connection_failure(text)

    def _show_status(self, status: ExchangeConnectionStatus) -> None:
        word = connection_word(status)
        problem = failure_text(status)
        logger.info(
            "[market] connection check: venue=%s reachable=%s failure=%s",
            status.venue.name,
            status.reachable,
            status.failure.name if status.failure is not None else None,
        )
        self.view.set_connection_text(word)
        if problem is None:
            self.view.log.append(word)
            return
        self.view.log.append(problem, "warning")
        self.view.show_connection_failure(problem)

    # -- the charts -----------------------------------------------------------

    def _open_chart(self, symbol: str) -> None:
        if symbol in self._charts:
            self.view.show_chart(symbol)
            return
        card = ChartCard(symbol)
        market = self.choice.current
        sources = ChartSources(
            self._deps.candles[market], ChartHistory(self._deps.history, market)
        )
        chart = MarketChart(card, self._deps, sources, symbol, self)
        chart.logged.connect(self.view.log.append)
        self._history.watch(chart)
        self._charts[symbol] = chart
        self.view.add_chart(symbol, card)
        self.closeChartEnabled.emit(True)
        chart.show_indicators(self._indicators)
        if self._live:
            chart.go_live()
        chart.show_symbol(symbol)
        logger.info("[market] chart opened for %s (live=%s)", symbol, self._live)

    def _close_chart(self, symbol: str) -> None:
        chart = self._charts.pop(symbol, None)
        if chart is None:
            return
        chart.shutdown()
        chart.release_stream()
        chart.deleteLater()
        self.view.remove_chart(symbol)
        self.closeChartEnabled.emit(bool(self._charts))
        logger.info("[market] chart closed for %s", symbol)

    def _show_indicators(self, keys: tuple[str, ...]) -> None:
        self._indicators = keys
        for chart in self._charts.values():
            chart.show_indicators(keys)
        logger.info("[market] indicators shown: %s", list(keys))

    def _redraw_indicator(self, key: str) -> None:
        """A script's parameters were edited: every chart drawing it redraws
        with the saved values."""
        for chart in self._charts.values():
            if key in chart.indicators:
                chart.redraw_indicators()
        logger.info("[market] indicator %s redrawn with its saved parameters", key)

    def _default_indicators(self) -> tuple[str, ...]:
        return tuple(
            key
            for key, script in self._deps.scripts.available().items()
            if script.default_enabled
        )

    def _indicator_choices(self) -> list[IndicatorChoice]:
        return [
            IndicatorChoice(key, script.title, key in self._indicators)
            for key, script in self._deps.scripts.available().items()
        ]

    # -- the stream -------------------------------------------------------------

    def _go_live(self) -> None:
        self._live = True
        self._start_watchlist_stream()
        for chart in self._charts.values():
            chart.go_live()

    def _start_watchlist_stream(self) -> None:
        """Streams the chosen market's symbols; a second start replaces the
        first (`IMarketStream.start`), so a new market needs no stop."""
        symbols = list(self._deps.symbols)
        outcome = self._deps.stream.start(
            WATCHLIST_STREAM_OWNER, self.choice.current, symbols, WATCHLIST_INTERVAL
        )
        if outcome.success:
            self.view.set_stream_text("Market data: live")
            self.view.log.append(f"Live for {', '.join(symbols)}.")
            return
        # SPEC-002 §4/§5: a stream that did not start says so, or it reads
        # as "no tick yet".
        logger.warning(
            "[market] watchlist stream did not start for %s: %s",
            symbols,
            outcome.message,
        )
        self.view.set_stream_text("Market data: failed to start")
        self.view.log.append(f"Failed to start stream: {outcome.message}", "error")

    def _on_tick(self, event: MarketTickEvent) -> None:
        if event.market_type is not self.choice.current:
            # The Feed asks the market on the bus's thread; a tick queued to
            # this thread before a switch lands after it (`EPIC-033Q`).
            return
        candle = event.market_data
        chart = self._charts.get(candle.symbol)
        if chart is not None:
            chart.apply_candle(candle)
        if candle.interval != WATCHLIST_INTERVAL.value:
            # A chart tab streams at its own timeframe; only the Watchlist's
            # own candles say its row's change (the PR #353 review).
            return
        if candle.open_price == 0.0:
            logger.warning(
                "[market] %s tick has a zero open price; its change is skipped",
                candle.symbol,
            )
            return
        change = (candle.close_price - candle.open_price) / candle.open_price * 100.0
        self.view.watchlist.update_tick(
            candle.symbol, candle.close_price, change, candle.volume
        )


def build_market_presenter(view: MarketView, container: IContainer) -> MarketPresenter:
    """The presenter factory the mode's contribution names (`Deferred`)."""
    return MarketPresenter(view, container, market_dependencies_for(container))
