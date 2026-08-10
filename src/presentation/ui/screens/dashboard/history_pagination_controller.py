from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject


class HistoryPaginationController(QObject):
    """
    @brief BOT-035 — when a chart card reports the user panned near the left
    edge of its loaded history, fetch one more batch of older candles.

    @details Owns exactly one concern: not tailing off a *second* fetch for
    a symbol while its first one is still in flight. It does not decide
    whether the user is "close enough" to the edge (EdgeScrollDetector's
    job) and does not know how to fetch or render anything (DashboardPresenter's
    job, via the injected `fetch_older` callback) — kept a thin, separate
    collaborator for the same reason AutoStartController is: SRP, and so a
    parallel task can work on either without touching the other's file.

    Per-symbol in-flight tracking (not a single presenter-wide flag) because
    the Dev Board's `active_charts` is keyed by symbol and each card scrolls
    independently — a lock scoped to one symbol must not block another.
    """

    def __init__(
        self,
        fetch_older: Callable[[str, float], None],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._fetch_older = fetch_older
        self._in_flight: set[str] = set()

    def on_near_left_edge(self, symbol: str, oldest_timestamp: float) -> None:
        """Connect to ChartCard.sig_near_left_edge (via the Presenter, which
        knows `oldest_timestamp` from that symbol's card). No-op if a fetch
        for this symbol is already running — safe to call repeatedly while
        the user keeps panning near the edge."""
        if symbol in self._in_flight:
            return
        self._in_flight.add(symbol)
        self._fetch_older(symbol, oldest_timestamp)

    def on_load_more_finished(self, symbol: str) -> None:
        """Call once the background fetch for `symbol` has fully settled —
        success, empty result, or error alike (mirrors
        ui_history_load_finished_signal's unconditional-finally contract).
        Safe to call even if `symbol` was never in flight."""
        self._in_flight.discard(symbol)
