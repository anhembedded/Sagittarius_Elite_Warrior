"""`EPIC-019A` — tradeable-symbol-list fetch/cache, pulled out of
`DashboardPresenter` and `BackTestPresenter`: both screens implemented the
same "check cache, submit a worker fetch, dispatch
`ListAvailableSymbolsQuery`, report ready/failed" sequence independently.

Mirrors the shape of `screens/dashboard/coordinators/indicator_coordinator.py`:
a plain class (not `QObject`), reached through injected callables rather than
holding a Presenter/View reference. Report channels are plain callables
(`emit_ready`/`emit_failed`) instead of Qt signals — a Coordinator owning Qt
signals would need to be a `QObject`, and each caller already has its own
signal to forward into, so there is nothing to gain from that here.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
)
from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger(__name__)


class SymbolOptionsCoordinator:
    """Fetches and caches the exchange's tradeable-symbol list for a symbol
    picker, first-open-only per session (a cache hit is a no-op)."""

    def __init__(
        self,
        dispatcher: IDispatcher,
        thread_manager: IThreadManager,
        emit_ready: Callable[[list[str]], None],
        emit_failed: Callable[[str], None],
    ) -> None:
        self._dispatcher = dispatcher
        self._thread_manager = thread_manager
        self._emit_ready = emit_ready
        self._emit_failed = emit_failed
        self._symbol_options_cache: list[str] | None = None

    def request_open(self) -> None:
        """Fetches the exchange's pair list the first time the picker opens
        in this session; a cache hit means a prior open already populated
        it and this is a no-op."""
        if self._symbol_options_cache is not None:
            return
        self._thread_manager.submit(self._fetch)

    def request_refresh(self) -> None:
        """Forces a refetch straight from the exchange, bypassing both this
        coordinator's cache and `ISymbolCatalogRepository`'s local one (the
        manual 🔄 in the picker, `BUG-066`)."""
        self._symbol_options_cache = None
        self._thread_manager.submit(lambda: self._fetch(force_refresh=True))

    def _fetch(self, force_refresh: bool = False) -> None:
        """Runs on a worker thread — hence reporting through callables that
        forward to Qt signals, rather than writing a ViewModel directly."""
        try:
            symbols = self._dispatcher.dispatch(
                ListAvailableSymbolsQuery,
                ListAvailableSymbolsQuery(force_refresh=force_refresh),
            )
        except Exception as exc:  # noqa: BLE001 - worker boundary, report don't crash
            logger.exception("Failed to fetch available symbols")
            self._emit_failed(str(exc))
            return
        self._emit_ready(symbols)

    def on_options_ready(self, symbols: list[str]) -> None:
        """Called from the main-thread slot connected to the caller's ready
        signal — updates the cache so the next `request_open()` is a no-op."""
        self._symbol_options_cache = symbols
