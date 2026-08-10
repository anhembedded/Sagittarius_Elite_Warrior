from __future__ import annotations

import time
from collections.abc import Callable

from PySide6.QtCore import QObject, QTimer

#: Minimum wall-clock gap between two fetches for the SAME symbol, measured
#: from when the previous one finished. Real usage found this necessary
#: (BOT-035 follow-up): EdgeScrollDetector fires on every real
#: sigRangeChangedManually — one continuous drag, or a single inertial
#: trackpad/wheel gesture, delivers many discrete events, not one. The
#: in-flight guard alone only stops *overlapping* fetches; the instant one
#: finishes, the next already-queued near-edge event would start another
#: immediately, so a user gently scrolling near the edge saw a new "Loaded N
#: older klines" log line roughly once a second for as long as they kept
#: scrolling. This cooldown collapses a burst of near-edge events into one
#: fetch per window instead of one per event.
_DEFAULT_COOLDOWN_SECONDS = 1.5


class HistoryPaginationController(QObject):
    """
    @brief BOT-035 — when a chart card reports the user panned near the left
    edge of its loaded history, fetch one more batch of older candles.

    @details Owns exactly two concerns: not tailing off a *second* fetch for
    a symbol while its first one is still in flight, and not immediately
    starting a third the moment the second finishes (see
    `_DEFAULT_COOLDOWN_SECONDS`). It does not decide whether the user is
    "close enough" to the edge (EdgeScrollDetector's job) and does not know
    how to fetch or render anything (DashboardPresenter's job, via the
    injected `fetch_older` callback) — kept a thin, separate collaborator
    for the same reason AutoStartController is: SRP, and so a parallel task
    can work on either without touching the other's file.

    Per-symbol tracking (not a single presenter-wide flag/timer) because the
    Dev Board's `active_charts` is keyed by symbol and each card scrolls
    independently — a lock/cooldown scoped to one symbol must not block
    another.
    """

    def __init__(
        self,
        fetch_older: Callable[[str, float], None],
        cooldown_seconds: float = _DEFAULT_COOLDOWN_SECONDS,
        recheck_edge: Callable[[str], None] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fetch_older = fetch_older
        self._cooldown_seconds = cooldown_seconds
        self._recheck_edge = recheck_edge
        self._in_flight: set[str] = set()
        #: Monotonic timestamp (time.monotonic(), not wall-clock — immune to
        #: system clock adjustments) of when the last fetch for this symbol
        #: finished. Absent until the first fetch completes.
        self._last_finished_at: dict[str, float] = {}

    def on_near_left_edge(self, symbol: str, oldest_timestamp: float) -> None:
        """Connect to ChartCard.sig_near_left_edge (via the Presenter, which
        knows `oldest_timestamp` from that symbol's card). No-op if a fetch
        for this symbol is already running, OR if the last one for this
        symbol finished too recently (see `_DEFAULT_COOLDOWN_SECONDS`) — safe
        to call repeatedly while the user keeps panning/scrolling near the
        edge."""
        if symbol in self._in_flight:
            return
        last_finished = self._last_finished_at.get(symbol)
        if (
            last_finished is not None
            and (time.monotonic() - last_finished) < self._cooldown_seconds
        ):
            return
        self._in_flight.add(symbol)
        self._fetch_older(symbol, oldest_timestamp)

    def on_load_more_finished(self, symbol: str) -> None:
        """Call once the background fetch for `symbol` has fully settled —
        success, empty result, or error alike (mirrors
        ui_history_load_finished_signal's unconditional-finally contract).
        Safe to call even if `symbol` was never in flight. Starts this
        symbol's cooldown window."""
        self._in_flight.discard(symbol)
        self._last_finished_at[symbol] = time.monotonic()

        QTimer.singleShot(
            int(self._cooldown_seconds * 1000),
            lambda: self._on_cooldown_finished(symbol),
        )

    def _on_cooldown_finished(self, symbol: str) -> None:
        """Called automatically when a symbol's cooldown window expires."""
        if self._recheck_edge is not None:
            self._recheck_edge(symbol)
