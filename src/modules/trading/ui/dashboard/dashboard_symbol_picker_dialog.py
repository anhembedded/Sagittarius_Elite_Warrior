"""Dev Board's symbol picker — the shared overlay, wired to this screen.

@par What it was, and why it is this now
It hosted `SymbolPicker.qml` and its docstring said why: *"Replaces
`SymbolPickerOverlay` for Dev Board (Dashboard), eliminating UI freeze when
displaying thousands of symbols via virtualized QML GridView."* That freeze was
real — the QtWidgets overlay built one `SymbolCard` widget per entry — so the app
carried two symbol pickers, one per toolkit. `EPIC-025` PR 4.3a made the shared
one virtualise on a `QTableView`; ADR D21 deletes the QML one, and this file is
what is left: the two pieces of wiring the shared component cannot own itself.

**What a choice means for this screen** (write the pair onto the ViewModel, note
it as recently used) and **where its data comes from**
(`DashboardSymbolPickerSource`). Both were already here; only the widget under
them changed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)

from .dashboard_symbol_picker_source import DashboardSymbolPickerSource

if TYPE_CHECKING:
    from .dashboard_view_model import DashboardQmlViewModel


class DashboardSymbolPickerDialog(SymbolPickerOverlay):
    """@brief Choose the Dev Board pair."""

    def __init__(
        self,
        view_model: DashboardQmlViewModel,
        preferences: SymbolPreferences,
        parent: QWidget | None = None,
    ) -> None:
        self._vm = view_model
        self._source = DashboardSymbolPickerSource(view_model, preferences)
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
        self.refresh_requested.connect(self._vm.symbolOptionsRefreshRequested)

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """Forward swapped preferences to the source adapter, which holds the
        only reference that matters."""
        self._preferences = preferences
        self._source.set_preferences(preferences)

    def open_dialog(self) -> None:
        self.show()
        self.raise_()

    def _on_favourite_toggled(self, symbol: str) -> None:
        self._source.set_favourite(symbol, not self._preferences.is_favourite(symbol))
        self.refresh()

    def _on_symbol_chosen(self, symbol: str) -> None:
        self._vm.symbol = symbol
        # Not part of `ISymbolPickerSource` — recents are host-driven, with no
        # picker-side write path — so this is the one call outside the
        # picker's own contract, kept so "Recent" goes on updating.
        self._preferences.note_used(symbol)
