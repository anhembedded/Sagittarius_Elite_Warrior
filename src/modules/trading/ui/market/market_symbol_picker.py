"""The shared symbol picker, wired to the Market mode (`EPIC-033V`).

The list is the chosen market's tradeable symbols, read once per market from
`ISymbolCatalog` by the shared `SymbolListReader` (off the UI thread, kept, so
typing in the picker never asks the exchange). Favourites and recents are the
app-wide `SymbolPreferences`.

One `SymbolPickerOverlay` is built for each opening, because what a choice
means differs by the command (open a chart, or add a row): the caller passes
that as `on_chosen`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolListReader,
    SymbolPickerOverlay,
    SymbolPreferences,
)
from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

from .market_choice import MARKET_TEXT
from .market_screen import MARKET_ROUTE

_HEADLINE = (
    "The {market} symbol list could not be read. Retry, or check the connection."
)


class MarketSymbolPicker(QObject):
    """@brief Opens the symbol picker over the chosen market's symbols."""

    def __init__(
        self,
        catalog: ISymbolCatalog,
        threads: IThreadManager,
        preferences: SymbolPreferences,
        notifier: INotifier,
        market: Callable[[], MarketType],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._preferences = preferences
        self._market = market
        self._reader: SymbolListReader[MarketType] = SymbolListReader(
            catalog.list_symbols,
            threads,
            notifier,
            cause="trading.market.symbols",
            scope=MARKET_ROUTE,
            parent=self,
        )

    def listed(self) -> Sequence[str]:
        """The chosen market's symbols, empty until its list has been read."""
        return self._reader.symbols(self._market())

    def read_symbols(self) -> None:
        market = self._market()
        self._reader.load(market, _HEADLINE.format(market=MARKET_TEXT[market]))

    def open(
        self,
        parent: QWidget | None,
        current: str,
        on_chosen: Callable[[str], None],
    ) -> SymbolPickerOverlay:
        """Opens a picker whose choice goes to `on_chosen`; `current` is the
        symbol it marks as the present one."""
        self.read_symbols()
        picker = SymbolPickerOverlay(
            self.listed,
            lambda: self._preferences.favourites,
            lambda: self._preferences.recents,
            lambda: current,
            parent,
        )
        picker.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        picker.refresh_requested.connect(self.read_symbols)
        self._reader.ready.connect(picker.refresh)
        picker.symbol_chosen.connect(self._preferences.note_used)
        picker.symbol_chosen.connect(on_chosen)
        picker.favourite_toggled.connect(self._preferences.toggle_favourite)
        picker.favourite_toggled.connect(lambda _symbol: picker.refresh())
        picker.open()
        return picker
