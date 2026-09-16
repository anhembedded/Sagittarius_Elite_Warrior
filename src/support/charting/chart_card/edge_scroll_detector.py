from __future__ import annotations

from collections.abc import Callable

from PySide6 import QtCore

#: How many candle-widths of empty space the user must be within (measured
#: from the left edge of the currently-loaded history) before this fires.
#: BOT-035 — chosen by the user: close enough that more data arrives before
#: the user can pan into empty space, far enough that idle panning near the
#: middle of the chart doesn't trigger a fetch.
_DEFAULT_EDGE_THRESHOLD_BARS = 20
_MINIMUM_CANDLES_FOR_EDGE_DETECTION = 2


class EdgeScrollDetector(QtCore.QObject):
    """
    @brief BOT-035 — watches for the user panning near the left edge of the
    currently-loaded candle history and reports it, nothing more.
    @details Deliberately does not decide whether a fetch should actually
    happen (debouncing, "one in flight at a time") — that's
    HistoryPaginationController's job. This class only answers "is the user
    close to running out of data to look at", so it stays reusable/testable
    independent of fetch/network concerns.

    Reads the candle history through a callback rather than owning it,
    because ChartCard (not this class) is the source of truth for
    `_raw_history` — this avoids a second, potentially-stale copy.
    """

    sig_near_left_edge = QtCore.Signal()

    def __init__(
        self,
        plot,
        get_raw_history: Callable[[], list[tuple[float, float, float, float, float]]],
        edge_threshold_bars: int = _DEFAULT_EDGE_THRESHOLD_BARS,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._plot = plot
        self._get_raw_history = get_raw_history
        self._edge_threshold_bars = edge_threshold_bars
        plot.vb.sigRangeChangedManually.connect(self.check_edge)

    def check_edge(self, *_args) -> None:
        """Evaluates whether the view is near the left edge, and emits sig_near_left_edge if so."""
        history = self._get_raw_history()
        if len(history) < _MINIMUM_CANDLES_FOR_EDGE_DETECTION:
            return

        oldest_timestamp = history[0][0]
        bar_width = history[1][0] - history[0][0]
        if bar_width <= 0:
            return

        (x_min, _x_max), _y_range = self._plot.vb.viewRange()
        if (x_min - oldest_timestamp) <= self._edge_threshold_bars * bar_width:
            self.sig_near_left_edge.emit()
