"""One chart tab of the Market mode (`EPIC-033H`): a symbol's candles, live,
with the indicator scripts the Indicators panel has checked.

The loading and the live candles are `LiveCandleChart`'s, as for a desk's
chart and a bot's (ADR D15). What a Market chart adds is the indicators: an
`IndicatorScriptRunner` of its own, replayed over the history it drew and
fed each closed candle after it. Every call reaches this object on the Qt
thread — the history through `LiveCandleChart`'s signal, a candle through the
presenter's Feed — so the runner draws as it computes.

A chart's own stream owner (`market.<symbol>`) keeps one tab's subscription
from replacing another's (the epic review of PR 300 found that with desks).

**Beyond the first window (`EPIC-033S`).** `load_older` asks for the window
right before the oldest candle drawn, as a pan past it does: the shared
chart's `older_candles` loads it from the store, else from the exchange
(`BUG-177`); `load_range` draws exactly a chosen span, read through
`ChartHistory` on the thread pool. The range comes back on a Qt signal
carrying the load's generation (`async-ui-action-rule.md` §1): asking for a
new first window (another timeframe, going live), drawing a range, or closing
the tab moves the generation on, and a result of an earlier one is dropped
and logged. The
chart counts as loading from the moment a first window is asked for until it
settles (drawn, empty or failed, `LiveCandleChart`'s two hooks), and while
its own load runs; nothing is asked against it meanwhile, and
`loadingChanged` says when. While a range is drawn the chart
draws no live candle, which would land after a gap the range does not show;
the next first window (View → Back to live, `EPIC-033T`, or a timeframe
change) follows the stream again, and `showingRangeChanged` says so.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal, SignalInstance
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.core.vo.timeframe import TimeFrame
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.contracts.i_candle_feed import (
    ICandleFeed,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.cancellable_report import (
    report_unless_cancelled,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_candle_chart import (
    LiveCandleChart,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from Sagittarius_Elite_Warrior.src.support.indicators.indicator_script_registry import (
    IndicatorScriptRegistry,
)
from Sagittarius_Elite_Warrior.src.support.indicators.ui.runner import (
    IndicatorScriptRunner,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

from .chart_history import ChartHistory, HistoryRange, RangeCandles
from .market_dependencies import MarketDependencies
from .market_screen import MARKET_ROUTE

logger = logging.getLogger("App.Trading.Market")


@dataclass(frozen=True)
class ChartSources:
    """Where one chart's candles come from: the live feed and the stored
    history, both of the market the mode shows (`EPIC-033Q`)."""

    feed: ICandleFeed
    history: ChartHistory
    market: MarketType


@dataclass(frozen=True)
class _LoadRequest:
    """What a load was asked against; its result fits only the same."""

    generation: int
    symbol: str
    interval: str


@dataclass(frozen=True)
class _Load:
    """One read for the worker: what to read, what it was asked against,
    where to report it, and whether the tab is still there to take it."""

    report: SignalInstance
    request: _LoadRequest
    read: Callable[[], object]
    token: CancellationToken


def stream_owner_for(symbol: str) -> str:
    """The chart's own owner on `IMarketStream`, one per open symbol."""
    return f"market.{symbol}"


class MarketChart(LiveCandleChart):
    """@brief One open symbol's `ChartCard`, loaded, live, with indicators."""

    #: Whether an older window or a range is loading.
    loadingChanged = Signal(bool)
    #: Whether a range is drawn in place of the live window.
    showingRangeChanged = Signal(bool)
    #: `(request, (span, RangeCandles) | error)`, from the worker thread.
    _range_loaded = Signal(object, object)

    def __init__(
        self,
        chart: ChartCard,
        dependencies: MarketDependencies,
        sources: ChartSources,
        symbol: str,
        notifier: INotifier,
        parent: QObject | None = None,
    ) -> None:
        """`sources` are of the market the mode shows (`EPIC-033Q`): a chart
        lives in one market, and a new market is a new chart."""
        super().__init__(
            chart,
            LiveChartPorts(
                thread_manager=dependencies.thread_manager,
                feed=sources.feed,
                stream_owner=stream_owner_for(symbol),
                interval=dependencies.interval,
                market=sources.market,
                notifier=notifier,
                scope=MARKET_ROUTE,
            ),
            parent,
        )
        self._scripts: IndicatorScriptRegistry = dependencies.scripts
        self._runner = IndicatorScriptRunner(
            registry=dependencies.scripts,
            emit_line=self._draw_line,
            emit_region=lambda key, spans: self._runner.draw_region(chart, key, spans),
            emit_info=lambda key, fields: self._runner.draw_info(chart, key, fields),
            emit_markers=lambda key, points: self._runner.draw_markers(
                chart, key, points
            ),
            on_error=self.logged.emit,
            notifier=notifier,
            scope=MARKET_ROUTE,
            get_params=dependencies.script_params,
        )
        self._indicators: tuple[str, ...] = ()
        self._klines: list[MarketData] = []
        self._threads = dependencies.thread_manager
        self._history_source = sources.history
        self._generation = 0
        self._load_token = CancellationToken()
        #: This chart's own load (older candles or a range) is running.
        self._own_load = False
        #: First windows asked for (`LiveCandleChart`) and not settled yet.
        self._first_windows = 0
        self._loading = False
        self._drawing_range = False
        self._showing_range = False
        self.older_candles.drawn.connect(self._on_older_drawn)
        self.older_candles.loadingChanged.connect(self._update_loading)
        self._range_loaded.connect(self._on_range_loaded)

    @property
    def chart(self) -> ChartCard:
        return self._chart

    @property
    def indicators(self) -> tuple[str, ...]:
        """The scripts drawn on this chart, in the order they were checked."""
        return self._indicators

    @property
    def loading(self) -> bool:
        """An older window or a range is loading, or a first window is: what
        is drawn is about to change, so nothing may be asked against it."""
        return self._loading

    @property
    def showing_range(self) -> bool:
        return self._showing_range

    def drawn_span(self) -> HistoryRange | None:
        """From the oldest drawn candle's open to the newest's close, or
        `None` while nothing is drawn."""
        if not self._klines:
            return None
        start, end = self._klines[0].open_time, self._klines[-1].close_time
        return HistoryRange(start, end) if start < end else None

    def redraw_indicators(self) -> None:
        """Recomputes the drawn scripts with their saved parameters, which
        each new instance reads (Tools → Indicator parameters…)."""
        self._replay()

    def show_indicators(self, keys: Iterable[str]) -> None:
        """Draws exactly `keys`, recomputed over the candles already drawn."""
        wanted = tuple(keys)
        if wanted == self._indicators:
            return
        self._indicators = wanted
        self._replay()

    # -- beyond the first window (`EPIC-033S`) ----------------------------

    def load_older(self) -> None:
        """Draws the window right before the oldest candle drawn, as a pan
        past it does."""
        if not self._loading:
            self.older_candles.request_now()

    def load_range(self, span: HistoryRange) -> None:
        """Draws exactly the stored candles of `span`, in place of what is
        drawn."""
        if self._loading or not self.shown_symbol:
            return
        request = self._drawn_request()
        interval = TimeFrame(request.interval)
        self._start_load(
            self._range_loaded,
            request,
            lambda: (
                span,
                self._history_source.in_range(request.symbol, interval, span),
            ),
        )

    def shutdown(self) -> None:
        """Also drops a load in flight: a closed tab draws nothing."""
        self._load_token.cancel()
        self._generation += 1
        self._own_load = False
        self._first_windows = 0
        self._update_loading()
        super().shutdown()

    def apply_candle(self, candle: MarketData) -> None:
        if self._showing_range:
            return
        super().apply_candle(candle)

    def _start_load(
        self, report: SignalInstance, request: _LoadRequest, read: Callable[[], object]
    ) -> None:
        self._own_load = True
        self._update_loading()
        self._load_token = CancellationToken()
        self._threads.submit(
            self._read_stored, _Load(report, request, read, self._load_token)
        )

    @staticmethod
    def _read_stored(load: _Load) -> None:
        """A worker thread: touches no widget, reports through a signal,
        never to a chart whose tab closed (its signal source may be gone)."""
        try:
            result: object = load.read()
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is reported, not lost to a thread's traceback
            result = exc
        report_unless_cancelled(load.token, load.report.emit, load.request, result)

    def _on_older_drawn(self, older: list[MarketData]) -> None:
        self._klines = older + self._klines
        self._replay()

    def _on_range_loaded(self, request: _LoadRequest, result: object) -> None:
        if not self._finish_own_load(request, "range"):
            return
        if isinstance(result, Exception):
            self.logged.emit(f"[ERROR] The range failed to load: {result}")
            return
        span, found = result if isinstance(result, tuple) else (None, None)
        if not isinstance(span, HistoryRange) or not isinstance(found, RangeCandles):
            return
        self._show_range(span, found)

    def _show_range(self, span: HistoryRange, found: RangeCandles) -> None:
        if not found.candles:
            self.logged.emit(
                f"No candles of {self.shown_symbol} are stored from "
                f"{write_value(ColumnKind.TIMESTAMP, span.start)} to "
                f"{write_value(ColumnKind.TIMESTAMP, span.end)} UTC."
            )
            return
        self._drawing_range = True
        try:
            self.draw_history(found.candles)
        finally:
            self._drawing_range = False
        logger.info(
            "[market] range of %s drawn: %d candles, cut=%s",
            self.shown_symbol,
            len(found.candles),
            found.cut,
        )
        text = (
            f"Showing {write_value(ColumnKind.QUANTITY, len(found.candles))} "
            f"candles of {self.shown_symbol} from "
            f"{write_value(ColumnKind.TIMESTAMP, span.start)} to "
            f"{write_value(ColumnKind.TIMESTAMP, span.end)} UTC."
        )
        if found.cut:
            text += " The range holds more; these are its newest."
        self.logged.emit(text)

    def _drawn_request(self) -> _LoadRequest:
        return _LoadRequest(self._generation, self.shown_symbol, self._interval)

    def _finish_own_load(self, request: _LoadRequest, what: str) -> bool:
        """The chart's own load is over, whatever its result; the result fits
        only what is drawn now: the same base (generation), symbol and
        timeframe as when it was asked for."""
        self._own_load = False
        self._update_loading()
        if request == self._drawn_request():
            return True
        logger.info("[market] stale %s load dropped: %s", what, request)
        return False

    def _update_loading(self) -> None:
        loading = (
            self._own_load or self._first_windows > 0 or self.older_candles.loading
        )
        if loading != self._loading:
            self._loading = loading
            self.loadingChanged.emit(loading)

    def _on_first_window_requested(self) -> None:
        # Asked, not yet drawn, is already a new base (the review of PR
        # #366): a load asked against the window it replaces must not land
        # after it, and none may start before it settles.
        self._generation += 1
        self._first_windows += 1
        self._update_loading()

    def _on_first_window_settled(self) -> None:
        self._first_windows = max(0, self._first_windows - 1)
        self._update_loading()

    def _on_history_drawn(self, klines: Sequence[MarketData]) -> None:
        # Any whole history drawn (a first window or a range) is a new base:
        # a load asked against the previous one no longer fits it.
        self._generation += 1
        if self._showing_range != self._drawing_range:
            self._showing_range = self._drawing_range
            self.showingRangeChanged.emit(self._showing_range)
        self._klines = list(klines)
        self._replay()

    def _on_candle_drawn(self, candle: MarketData) -> None:
        if not candle.is_closed:
            return
        self._klines.append(candle)
        self._runner.feed(candle)

    def _draw_line(self, name: str, x_data: list, y_data: list) -> None:
        self._runner.draw(self._chart, name, x_data, y_data)

    def _replay(self) -> None:
        # Scripts carry warm-up state and have no reset: a new set is new
        # instances, fed the whole history (`IndicatorScriptRunner.rebuild`).
        self._runner.clear_from_chart(self._chart)
        self._runner.rebuild(self._indicators)
        self._runner.feed_all(self._klines)
