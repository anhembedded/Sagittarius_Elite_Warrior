"""Dashboard symbol picker — hosts the standalone `SymbolPicker.qml`.

Replaces `SymbolPickerOverlay` for Dev Board (Dashboard), eliminating UI freeze
when displaying thousands of symbols via virtualized QML GridView.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.symbol_picker import (
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_modal_host import (
    SymbolPickerModal,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SymbolPicker.symbol_picker_vm import (
    SymbolPickerVM,
)

from .dashboard_symbol_picker_source import DashboardSymbolPickerSource

if TYPE_CHECKING:
    from .dashboard_view_model import DashboardQmlViewModel


class DashboardSymbolPickerDialog(SymbolPickerModal):
    """
    @brief Choose the Dev Board pair. Chrome+modal is `SymbolPickerModal`, body is
    `SymbolPicker.qml`, rules are `SymbolPickerVM` reading through
    `DashboardSymbolPickerSource`.
    """

    def __init__(
        self,
        view_model: DashboardQmlViewModel,
        preferences: SymbolPreferences,
        parent: QWidget | None = None,
    ) -> None:
        self._vm = view_model
        self._source = DashboardSymbolPickerSource(view_model, preferences)
        self._preferences = preferences
        self._widget_vm = SymbolPickerVM(self._source)
        super().__init__(self._widget_vm, parent=parent)

        self.symbolChosen.connect(self._on_symbol_chosen)
        self.refreshRequested.connect(self._on_refresh_requested)

    def _on_refresh_requested(self) -> None:
        self._vm.symbolOptionsRefreshRequested.emit()

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """Forward swapped preferences to the source adapter."""
        self._preferences = preferences
        self._source.set_preferences(preferences)

    def open_dialog(self) -> None:
        self.show()
        self.raise_()

    def refresh(self) -> None:
        """Re-reads `symbolOptions` and re-renders while open."""
        self._widget_vm.refresh()

    def _on_symbol_chosen(self, symbol: str) -> None:
        self._vm.symbol = symbol
        self._preferences.note_used(symbol)
