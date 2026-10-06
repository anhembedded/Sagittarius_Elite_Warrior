"""`UiThreadRelay` — a worker's answer, handed to the UI thread by Qt.

A worker on the app's pool calls `_report(payload)`; the private `_done`
signal is queued to the thread this object lives on (the UI thread), where
`_deliver(payload)` runs. The relay has no Qt parent on purpose: a parent
torn down while a worker is still running would delete the object the
worker is about to emit on, and the worker's own reference keeps a
parentless relay alive until it returns. What a late answer means (stale,
dropped after shutdown) is each subclass's `_deliver` to decide.

Shared by the Bots screen's `FencedReads` and the Market Watchlist's
`WatchlistFilters` (review of PR #374), so the hand-off is written once.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class UiThreadRelay(QObject):
    """@brief Runs `_deliver` on the UI thread for each worker `_report`."""

    _done = Signal(object)

    def __init__(self) -> None:
        super().__init__()
        self._done.connect(self._deliver)

    def _report(self, payload: object) -> None:
        """Called on a worker thread; never touches a widget."""
        self._done.emit(payload)

    def _deliver(self, payload: object) -> None:
        """Runs on the UI thread with what the worker reported."""
        raise NotImplementedError
