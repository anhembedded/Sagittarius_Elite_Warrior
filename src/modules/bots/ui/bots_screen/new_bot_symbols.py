"""`BUG-155` — the symbols New bot's picker lists for the chosen venue's market, read off the
UI thread.

The shared `SymbolPickerOverlay` asks its host for four things; the symbol
list is the one that can need the exchange. It is read through the published
`ISymbolCatalog` on the thread pool and handed to the picker through a queued
Qt signal, so opening New bot never waits on the network. Favourites and
recents are the shared `SymbolPreferences` store.

The list is the market of the venue the dialog is on (`use_venue`, `EPIC-039J`): a Futures
venue lists Futures symbols, each market read once and kept.
"""

from __future__ import annotations

import logging
from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import (
    FailureKind,
    FailureNotice,
    INotifier,
    failure_detail,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_profile import (
    BOT_MARKET,
    SPOT_TITLE,
    market_of,
    title_word_of,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_screen import (
    BOTS_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPreferences,
    find_symbol_preferences,
)
from sagittarius_engine.interfaces.i_container import IContainer
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

logger = logging.getLogger("App.Bots.NewBot")

_CATALOG_CAUSE = "bots.read.symbols"
_CATALOG_HEADLINE = (
    "The {title} symbol list could not be read. Retry, or check the connection."
)


class NewBotSymbols(QObject):
    """@brief The catalog of the chosen venue's market, favourites and recents the New bot
    picker reads."""

    #: Emitted on the main thread when the catalog has been read.
    catalog_ready = Signal()
    #: Emitted on the main thread when the catalog could not be read; the
    #: message bar carries why (`BOT-169`).
    catalog_failed = Signal()

    # Worker-thread side of the read; the queued connection moves each answer
    # onto the main thread.
    _catalog_read = Signal(object, list)

    def __init__(
        self,
        catalog: ISymbolCatalog,
        threads: IThreadManager,
        preferences: SymbolPreferences,
        notifier: INotifier,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._notifier = notifier
        self._catalog = catalog
        self._threads = threads
        self._preferences = preferences
        self._listed: dict[MarketType, list[str]] = {}
        self._asked: set[MarketType] = set()
        self._market = BOT_MARKET
        self._title = SPOT_TITLE
        self._catalog_read.connect(self._on_catalog_read)

    def use_venue(self, venue: TradingVenue) -> None:
        """The venue the dialog is on now: the picker lists its market's symbols."""
        self._market = market_of(venue)
        self._title = title_word_of(venue)

    def catalog_symbols(self) -> Sequence[str]:
        return self._listed.get(self._market, [])

    def starred(self) -> Sequence[str]:
        return self._preferences.favourites

    def recent(self) -> Sequence[str]:
        return self._preferences.recents

    def load_catalog(self) -> None:
        """Reads the catalog the first time the picker opens; later opens
        reuse it. A failed read is asked again on the next open."""
        market, title = self._market, self._title
        if market in self._asked:
            return
        self._asked.add(market)
        self._threads.submit(self._read_catalog_off_thread, market, title)

    def toggle_star(self, symbol: str) -> None:
        self._preferences.toggle_favourite(symbol)

    def note_used(self, symbol: str) -> None:
        self._preferences.note_used(symbol)

    def _read_catalog_off_thread(self, market: MarketType, title: str) -> None:
        """Runs on a worker thread; reports only through signals."""
        try:
            symbols = list(self._catalog.list_symbols(market))
        except Exception as exc:
            logger.exception("Could not read the %s symbol list", title)
            self._asked.discard(market)
            self._notifier.report_failure(
                FailureNotice(
                    FailureKind.BACKGROUND,
                    _CATALOG_CAUSE,
                    _CATALOG_HEADLINE.format(title=title),
                    scope=BOTS_ROUTE,
                    detail=failure_detail(exc),
                    retry=self.load_catalog,
                )
            )
            self.catalog_failed.emit()
            return
        self._catalog_read.emit(market, symbols)

    def _on_catalog_read(self, market: MarketType, symbols: list[str]) -> None:
        self._listed[market] = symbols
        self._notifier.clear_failure(_CATALOG_CAUSE)
        self.catalog_ready.emit()


def new_bot_symbols(
    catalog: ISymbolCatalog,
    threads: IThreadManager,
    container: IContainer,
    notifier: INotifier,
) -> NewBotSymbols:
    """The picker's data, on the app-wide favourites and recents when the
    container holds them."""
    preferences = find_symbol_preferences(container) or SymbolPreferences()
    return NewBotSymbols(catalog, threads, preferences, notifier)
