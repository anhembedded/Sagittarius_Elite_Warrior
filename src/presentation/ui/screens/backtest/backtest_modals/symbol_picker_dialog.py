"""Backtest's symbol picker — the shared overlay, wired to this screen.

@par What it was, and why it is this now
`EPIC-015` made this screen host `SymbolPicker.qml` while Data Management kept
the QtWidgets `SymbolPickerOverlay`, which left the app with two symbol pickers,
one per toolkit. The QML one existed to escape a real freeze: the QtWidgets
overlay built one `SymbolCard` widget per entry, and the exchange lists about
fourteen hundred pairs. `EPIC-025` PR 4.3a made the shared overlay virtualise on
a `QTableView`, ADR D21 deletes the QML one, and what is left here is the wiring
the shared component cannot own itself — the same wiring this file always owned,
under a different widget.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)

from .backtest_symbol_picker_source import BacktestSymbolPickerSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class SymbolPickerDialogWidget(SymbolPickerOverlay):
    """@brief Choose the Backtest chart's symbol.

    @details Owns the one piece of wiring the shared component cannot own
    itself: what a *choice* means for this screen. The ViewModel write happens
    here, in the composition root — not pushed down into the source adapter
    nor up into `BackTestModalsHost`.
    """

    def __init__(
        self,
        view_model: BackTestViewModel,
        preferences: SymbolPreferences,
        parent: QWidget | None = None,
    ) -> None:
        self._vm = view_model
        self._source = BacktestSymbolPickerSource(view_model, preferences)
        self._preferences = preferences
        super().__init__(
            get_symbols=self._source.get_symbols,
            get_favourites=self._source.get_favourites,
            get_recents=self._source.get_recents,
            get_current=self._source.get_current,
            parent=parent,
        )

        self.symbol_chosen.connect(self._on_symbol_chosen)
        self.favourite_toggled.connect(self._on_favourite_toggled)
        self.refresh_requested.connect(self._vm.refreshSymbolOptionsRequested)

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """`BackTestModalsHost.set_symbol_preferences`'s seam — forwarded to
        the source adapter, which holds the only reference that matters."""
        self._preferences = preferences
        self._source.set_preferences(preferences)

    def open_dialog(self) -> None:
        self.show()
        self.raise_()

    def _on_favourite_toggled(self, symbol: str) -> None:
        self._source.set_favourite(symbol, not self._preferences.is_favourite(symbol))
        self.refresh()

    def _on_symbol_chosen(self, symbol: str) -> None:
        self._vm.selectedSymbol = symbol
        # Not part of `ISymbolPickerSource` — recents are host-driven, with no
        # picker-side write path — so this is the one call outside the
        # picker's own contract, kept so "Recent" goes on updating (BOT-102's
        # `refresh()` is now the base class's).
        self._preferences.note_used(symbol)
