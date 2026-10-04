"""`EPIC-029D` — runs a Grid backtest or a candle sync off the UI thread.

Owns no action-id bookkeeping and no state the screen shows
(`async-ui-action-rule.md` §2): the presenter's tracker issues the id, this
runs the work on the thread manager and hands back `(action_id, answer,
error)` on the Qt thread. Cancellation is the one thing it holds: each run
gets its own `threading.Event`, which the query and the sync poll between
candles and between fetches, so `stop()` ends the run in flight and only
that run.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from dataclasses import replace

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.queries.run_grid_backtest import (
    RunGridBacktestQuery,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sync import (
    IMarketDataSync,
    MarketDataSyncRequest,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.Backtest")

#: A sync finished: what the coordinator answers in place of a result.
SYNCED = "synced"


class GridBacktestCoordinator(QObject):
    """@brief One backtest or sync at a time, cancellable, answered on Qt."""

    #: The action id, the answer (or `None`), and an error in words (or "").
    finished = Signal(int, object, str)
    _done = Signal(int, object, str)

    def __init__(
        self,
        threads: IThreadManager,
        dispatcher: ICommandDispatcher,
        sync: IMarketDataSync,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._threads = threads
        self._dispatcher = dispatcher
        self._sync = sync
        self._cancel = threading.Event()
        self._done.connect(self.finished)

    def start_backtest(self, action_id: int, query: RunGridBacktestQuery) -> None:
        cancel = self._fresh_cancel()
        request = replace(query, cancelled=cancel.is_set)
        dispatcher = self._dispatcher
        self._submit(
            action_id, lambda: dispatcher.dispatch(RunGridBacktestQuery, request)
        )

    def start_sync(
        self, action_id: int, requests: tuple[MarketDataSyncRequest, ...]
    ) -> None:
        cancel = self._fresh_cancel()
        sync = self._sync

        def work() -> str:
            for request in requests:
                if cancel.is_set():
                    break
                sync.sync(replace(request, cancellation_requested=cancel.is_set))
            return SYNCED

        self._submit(action_id, work)

    def stop(self) -> None:
        """Stops the run in flight; idempotent."""
        self._cancel.set()

    def _fresh_cancel(self) -> threading.Event:
        self._cancel.set()
        self._cancel = threading.Event()
        return self._cancel

    def _submit(self, action_id: int, work: Callable[[], object]) -> None:
        self._threads.submit(self._on_pool, action_id, work)

    def _on_pool(self, action_id: int, work: Callable[[], object]) -> None:
        try:
            self._done.emit(action_id, work(), "")
        except Exception as exc:  # noqa: BLE001 - worker boundary: the failure is shown in words, not lost to a pool thread
            logger.warning("Grid backtest work %s failed: %s", action_id, exc)
            self._done.emit(action_id, None, str(exc) or type(exc).__name__)
