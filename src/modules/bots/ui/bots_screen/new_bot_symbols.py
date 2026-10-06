"""`BUG-155` — the Spot symbols New bot's picker lists, read off the UI thread.

The shared `SymbolPickerOverlay` asks its host for four things; the symbol
list is the one that can need the exchange. It is read through the published
`ISymbolCatalog` on the thread pool and handed to the picker through a queued
Qt signal, so opening New bot never waits on the network. Favourites and
recents are the shared `SymbolPreferences` store.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
    find_symbol_preferences,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.NewBot")


class NewBotSymbols(QObject):
    """@brief The Spot catalog, favourites and recents the New bot picker reads."""

    #: Emitted on the main thread when the catalog has been read.
    catalog_ready = Signal()
    #: Emitted on the main thread with why the catalog could not be read.
    catalog_failed = Signal(str)

    # Worker-thread side of the read; the queued connection moves each answer
    # onto the main thread.
    _catalog_read = Signal(list)

    def __init__(
        self,
        catalog: ISymbolCatalog,
        threads: IThreadManager,
        preferences: SymbolPreferences,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._catalog = catalog
        self._threads = threads
        self._preferences = preferences
        self._listed: list[str] | None = None
        self._asked = False
        self._catalog_read.connect(self._on_catalog_read)

    def catalog_symbols(self) -> Sequence[str]:
        return self._listed or []

    def starred(self) -> Sequence[str]:
        return self._preferences.favourites

    def recent(self) -> Sequence[str]:
        return self._preferences.recents

    def load_catalog(self) -> None:
        """Reads the catalog the first time the picker opens; later opens
        reuse it. A failed read is asked again on the next open."""
        if self._asked:
            return
        self._asked = True
        self._threads.submit(self._read_catalog_off_thread)

    def toggle_star(self, symbol: str) -> None:
        self._preferences.toggle_favourite(symbol)

    def note_used(self, symbol: str) -> None:
        self._preferences.note_used(symbol)

    def _read_catalog_off_thread(self) -> None:
        """Runs on a worker thread; reports only through signals."""
        try:
            symbols = list(self._catalog.list_symbols(MarketType.SPOT))
        except Exception as exc:
            logger.exception("Could not read the Spot symbol list")
            self._asked = False
            self.catalog_failed.emit(str(exc))
            return
        self._catalog_read.emit(symbols)

    def _on_catalog_read(self, symbols: list[str]) -> None:
        self._listed = symbols
        self.catalog_ready.emit()


def new_bot_symbols(
    catalog: ISymbolCatalog, threads: IThreadManager, container: IContainer
) -> NewBotSymbols:
    """The picker's data, on the app-wide favourites and recents when the
    container holds them."""
    return NewBotSymbols(
        catalog, threads, find_symbol_preferences(container) or SymbolPreferences()
    )
