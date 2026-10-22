"""`BOT-233` — the stored candles of the period the workbench is set to, read before any run.

A person designing a grid wants to see the price history under it, with no parameters set. This reads
the candles stored for the followed bot's venue, symbol, interval and period (`GetStoredCandlesQuery`)
off the UI thread, and answers on Qt with the window it read, so the page can draw them and say how much
of the period is stored. It never fetches: Sync candles does, through the same sync a run's refusal
offers (`async-ui-action-rule.md`).

It is a read with its own fence, apart from the run's one-action-at-a-time tracker: a read is cheap and
changing the interval or the period asks for another, which supersedes the one in flight (an answer for
a window no longer asked for is dropped and logged).
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import failure_detail
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.get_stored_candles import (
    GetStoredCandlesQuery,
    StoredCandles,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.candle_window import (
    CandleWindow,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.Backtest")

_KIND = "backtest_candles"

#: The one query the preview runs; the host binds it to the dispatcher, as for a run.
type StoredCandlesReader = Callable[[GetStoredCandlesQuery], StoredCandles]


class CandlePreview(QObject):
    """@brief Reads one window's stored candles at a time and says what it found."""

    #: The window read, what was stored (or `None` when the read raised) and a failure's detail.
    loaded = Signal(object, object, str)
    #: The pool thread's answer, queued onto the Qt thread: the action id, the answer, the detail.
    _done = Signal(int, object, str)

    def __init__(self, threads: IThreadManager, read: StoredCandlesReader) -> None:
        super().__init__()
        self._threads = threads
        self._read = read
        self._tracker: ActionOwnershipTracker[str, str, None] = ActionOwnershipTracker()
        self._windows: dict[int, CandleWindow] = {}
        self._wanted: CandleWindow | None = None
        self._found: StoredCandles | None = None
        self._closed = False
        self._done.connect(self._on_answer)

    @property
    def wanted(self) -> CandleWindow | None:
        """The window now asked for."""
        return self._wanted

    @property
    def found(self) -> StoredCandles | None:
        """What is stored for `wanted`; `None` while it is read, when it could not be, or with none asked."""
        return self._found

    @property
    def is_reading(self) -> bool:
        return self._wanted is not None and self._found is None and self._pending()

    def want(self, window: CandleWindow | None) -> bool:
        """Asks for `window`'s candles. @return whether the window is another one, so the page draws
        what it has (nothing yet) while they are read; the same window again changes nothing."""
        if window == self._wanted:
            return False
        self._wanted, self._found = window, None
        self._tracker.invalidate_active()
        if window is None:
            return True
        action = self._tracker.begin_action(_KIND, window.interval.value, None)
        self._windows[action.action_id] = window
        query = GetStoredCandlesQuery(
            window.venue, window.symbol, window.interval, window.start, window.end
        )
        logger.debug(
            "Candle preview %s: %s %s",
            action.action_id,
            window.symbol,
            window.interval.value,
        )
        self._threads.submit(self._on_pool, action.action_id, query)
        return True

    def reload(self) -> None:
        """Reads the window again (after a sync stored more)."""
        window = self._wanted
        self.forget()
        self.want(window)

    def forget(self) -> None:
        """Drops the window and what was read for it, so the next `want` of any window reads."""
        self._wanted = self._found = None
        self._tracker.invalidate_active()

    def close(self) -> None:
        self._closed = True
        self._tracker.invalidate_active()

    def _pending(self) -> bool:
        return self._tracker.active_outcome is ActionOutcome.PENDING

    def _on_pool(self, action_id: int, query: GetStoredCandlesQuery) -> None:
        found: StoredCandles | None = None
        detail = ""
        try:
            found = self._read(query)
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is shown in words, not lost to a pool thread
            logger.warning("Candle preview %s failed: %s", action_id, exc)
            detail = failure_detail(exc)
        if not self._closed:
            self._done.emit(action_id, found, detail)

    def _on_answer(
        self, action_id: int, found: StoredCandles | None, detail: str
    ) -> None:
        window = self._windows.pop(action_id, None)
        if window is None or not self._tracker.is_current_pending(action_id, _KIND):
            self._tracker.log_stale_callback("_on_answer", action_id, _KIND)
            return
        self._tracker.finish_action(
            action_id, ActionOutcome.FAILED if detail else ActionOutcome.SUCCEEDED
        )
        self._found = found
        self.loaded.emit(window, found, detail)
