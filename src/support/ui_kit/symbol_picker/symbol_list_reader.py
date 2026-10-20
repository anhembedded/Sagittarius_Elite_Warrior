"""A symbol list read off the UI thread, once per key, for a picker to show.

The shared `SymbolPickerOverlay` asks its host for the symbols; the list is
the part that can need the exchange. A host reads it here, on the thread pool,
and the answer reaches the main thread through a queued signal, so opening a
picker never waits on the network and typing in it never asks the exchange.
The key is whatever the list depends on (a market); each key is read once and
kept, and a failed read is told through the `INotifier` with a Retry and
asked again on the next `load`.

Support imports no module, so the read itself is the caller's callable.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Hashable, Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.UiKit.SymbolPicker")


class SymbolListReader[K: Hashable](QObject):
    """@brief The symbols of each key, read once off the UI thread."""

    #: Emitted on the main thread when a key's list has been read.
    ready = Signal()
    #: Emitted on the main thread when a read failed.
    failed = Signal()

    # Worker-thread side of the read; the queued connection moves each answer
    # onto the main thread.
    _read_done = Signal(object, list)

    def __init__(
        self,
        read: Callable[[K], Sequence[str]],
        threads: IThreadManager,
        notifier: INotifier,
        *,
        cause: str,
        scope: str,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._read = read
        self._threads = threads
        self._notifier = notifier
        self._cause = cause
        self._scope = scope
        self._listed: dict[K, list[str]] = {}
        self._asked: set[K] = set()
        self._read_done.connect(self._on_read_done)

    def symbols(self, key: K) -> Sequence[str]:
        """The key's symbols; empty until its list has been read."""
        return self._listed.get(key, [])

    def load(self, key: K, headline: str) -> None:
        """Reads the key's list the first time; later calls reuse it.
        `headline` says what failed and what to do if the read does."""
        if key in self._asked:
            return
        self._asked.add(key)
        self._threads.submit(self._read_off_thread, key, headline)

    def _read_off_thread(self, key: K, headline: str) -> None:
        """Runs on a worker thread; reports only through signals."""
        try:
            symbols = list(self._read(key))
        except Exception as exc:
            logger.exception(
                "[symbol-list] could not read %s (cause %s)", key, self._cause
            )
            self._asked.discard(key)
            self._notifier.report_failure(
                FailureNotice(
                    FailureKind.BACKGROUND,
                    self._cause,
                    headline,
                    scope=self._scope,
                    detail=failure_detail(exc),
                    retry=lambda: self.load(key, headline),
                )
            )
            self.failed.emit()
            return
        self._read_done.emit(key, symbols)

    def _on_read_done(self, key: K, symbols: list[str]) -> None:
        self._listed[key] = symbols
        self._notifier.clear_failure(self._cause)
        logger.info("[symbol-list] %d symbols listed for %s", len(symbols), key)
        self.ready.emit()
