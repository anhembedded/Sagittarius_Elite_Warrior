"""`BUG-177` — older candles for a live chart: when the user pans or zooms past
the oldest candle drawn, the window right before it is loaded (from the store,
else from the exchange, `ICandleFeed.load_older`) and drawn to its left.

@details The chart reports the pan (`ChartCard.sig_near_left_edge`); this
object decides whether to ask, draws the answer and keeps the one-at-a-time
bookkeeping, so every `LiveCandleChart` (a desk's, a bot's, a Market tab's) gets
it from one place. The Dev Board's `HistoryPaginationController` did this for the
board's charts alone and went with the board (`c7914f0`); the shared chart never
had it.

**What a pan does and does not ask.** One load at a time per chart; after one
settles, no new pan asks for `OLDER_COOLDOWN_SECONDS` (one drag fires many
range events), and after one that found nothing older (the start of the
market's history, or a sync the exchange refused) for
`EMPTY_COOLDOWN_SECONDS`, so a chart at the start of its data does not call the
exchange on every pan. A command (`request_now`) is not held by either.

**Fenced by the request.** A load carries the chart's token of its first
window; a new first window (another symbol or timeframe, going live, a closed
tab) cancels that token, `reset()` forgets the load, and an answer that was on
its way is dropped (`async-ui-action-rule.md` §1).

**What is drawn.** Only candles that open before the oldest one drawn, so a
candle loaded twice, or one a live tick drew meanwhile, is never drawn again;
the view the user is looking at does not move (`ChartCard.prepend_historical_*`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.src.support.charting.chart_card import ChartCard
from Sagittarius_Elite_Warrior.src.support.charting.chart_card.kline_mapping import (
    map_klines,
    map_volume,
)
from Sagittarius_Elite_Warrior.src.support.charting.live_chart.live_chart_ports import (
    LiveChartPorts,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken

logger = logging.getLogger("App.OlderCandlesBackfill")

#: Between two loads: a drag or an inertial wheel gesture fires many range
#: events, and the first load already moves the edge far away (`BOT-035`).
OLDER_COOLDOWN_SECONDS = 1.5
#: After a load that found nothing older.
EMPTY_COOLDOWN_SECONDS = 30.0


@dataclass(frozen=True, slots=True)
class ShownWindow:
    """What the chart shows now, and the token of the first window that drew
    it: a load asked against it is dropped when the token is cancelled."""

    symbol: str
    interval: str
    token: CancellationToken


@dataclass(frozen=True, slots=True)
class BackfillHooks:
    """What the backfill needs from the chart that owns it."""

    #: The shown window, or `None` while there is nothing to extend (no symbol
    #: shown, or a first window is on its way and about to replace what is drawn).
    window: Callable[[], ShownWindow | None]
    #: Submits the load of the window right before `before`.
    start: Callable[[ShownWindow, datetime], None]


class OlderCandlesBackfill(QObject):
    """@brief Asks for, draws and tells about one chart's older candles."""

    #: A line for the owner's log.
    logged = Signal(str)
    #: Whether a load is running: it started or settled.
    loadingChanged = Signal(bool)
    #: Older candles were drawn, oldest first: for what the owner draws over them.
    drawn = Signal(list)
    #: The coordinator's reports, from its worker thread; Qt queues them to
    #: this object's (the UI) thread.
    _arrived = Signal(object, list)
    _lost = Signal(object, str, str)

    def __init__(
        self,
        chart: ChartCard,
        ports: LiveChartPorts,
        hooks: BackfillHooks,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._chart = chart
        self._hooks = hooks
        self._notifier, self._scope = ports.notifier, ports.scope
        self._cause = f"charting.older_candles.{ports.stream_owner}"
        self._clock: Callable[[], float] = ports.clock
        self._oldest: datetime | None = None
        self._asked: ShownWindow | None = None
        self._not_before = 0.0
        #: A failure bar of this chart's is up, for the retry or the next success
        #: to take down.
        self._told = False
        self._arrived.connect(self._on_arrived)
        self._lost.connect(self._on_lost)
        chart.sig_near_left_edge.connect(self._on_near_left_edge)

    @property
    def loading(self) -> bool:
        return self._asked is not None

    def deliver_ready(self, token: CancellationToken, rows: list) -> None:
        """For `LiveChartCallbacks.older_ready`; any thread."""
        self._arrived.emit(token, rows)

    def deliver_failed(
        self, token: CancellationToken, headline: str, detail: str
    ) -> None:
        """For `LiveChartCallbacks.older_failed`; any thread."""
        self._lost.emit(token, headline, detail)

    def note_drawn(self, klines: Sequence[MarketData]) -> None:
        """A whole history was drawn (a first window, or a range): its oldest
        candle is the one the next window ends before, and a window asked
        against what it replaced no longer joins what is drawn."""
        self._oldest = klines[0].open_time if klines else None
        if self.loading:
            self._asked = None
            self.loadingChanged.emit(False)

    def reset(self) -> None:
        """A first window was asked for, or the chart closed: what was asked
        no longer fits what is drawn, and its failure bar has no chart to
        retry on."""
        loading = self.loading
        self._asked = None
        self._not_before = 0.0
        self._clear_failure()
        if loading:
            self.loadingChanged.emit(False)

    def request_now(self) -> None:
        """The user asked for older candles (View → Load older): held by
        neither cooldown, only by a load already running."""
        window = self._hooks.window()
        if window is not None:
            self._begin(window)

    def _on_near_left_edge(self, symbol: str) -> None:
        window = self._hooks.window()
        if window is None or window.symbol != symbol:
            return
        if self._clock() < self._not_before:
            return
        self._begin(window)

    def _begin(self, window: ShownWindow) -> None:
        if self._oldest is None or self._asked is not None:
            return
        self._asked = window
        logger.info(
            "[older-candles] %s %s: asking for candles before %s",
            window.symbol,
            window.interval,
            self._oldest.isoformat(),
        )
        self._hooks.start(window, self._oldest)
        self.loadingChanged.emit(True)

    def _on_arrived(self, token: object, rows: list) -> None:
        window = self._settle(token, OLDER_COOLDOWN_SECONDS)
        if window is None:
            return
        self._clear_failure()
        fresh = [row for row in rows if self._oldest and row.open_time < self._oldest]
        if not fresh:
            self._not_before = self._clock() + EMPTY_COOLDOWN_SECONDS
            logger.info(
                "[older-candles] %s %s: nothing older", window.symbol, window.interval
            )
            self.logged.emit(f"No older candles of {window.symbol} are available.")
            return
        self._chart.prepend_historical_data(map_klines(fresh))
        self._chart.prepend_historical_volume(map_volume(fresh))
        self._oldest = fresh[0].open_time
        self.drawn.emit(fresh)
        logger.info(
            "[older-candles] %s %s: %d candles drawn before the oldest",
            window.symbol,
            window.interval,
            len(fresh),
        )
        self.logged.emit(f"Loaded {len(fresh)} older candles of {window.symbol}.")

    def _on_lost(self, token: object, headline: str, detail: str) -> None:
        if self._settle(token, OLDER_COOLDOWN_SECONDS) is None:
            return
        self.logged.emit(f"[ERROR] {headline}")
        self._told = True
        self._notifier.report_failure(
            FailureNotice(
                kind=FailureKind.BACKGROUND,
                cause=self._cause,
                headline=headline,
                scope=self._scope,
                detail=detail,
                retry=self.request_now,
            )
        )

    def _clear_failure(self) -> None:
        if self._told:
            self._told = False
            self._notifier.clear_failure(self._cause)

    def _settle(self, token: object, cooldown: float) -> ShownWindow | None:
        """The load asked for is over: the window it was asked against, or
        `None` when `token` is not that load's (a request since replaced)."""
        window = self._asked
        if window is None or window.token is not token:
            return None
        self._asked = None
        self._not_before = self._clock() + cooldown
        self.loadingChanged.emit(False)
        return window
