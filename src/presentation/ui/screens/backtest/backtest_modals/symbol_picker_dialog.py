"""Backtest symbol picker — `EPIC-015`: hosts the standalone `SymbolPicker.qml`.

Replaces `SymbolPickerOverlay` for Backtest only (Data Management and Dev
Board keep the QtWidgets overlay for now — see `EPIC-015`'s README for the
per-screen rollout order).
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

from .backtest_symbol_picker_source import BacktestSymbolPickerSource

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class SymbolPickerDialogWidget(SymbolPickerModal):
    """
    @brief Choose the Backtest chart's symbol. Chrome+modal is
    `SymbolPickerModal`, body is `SymbolPicker.qml`, rules are
    `SymbolPickerVM` reading through `BacktestSymbolPickerSource`.

    @details `EPIC-015`'s Backtest leg of `SymbolPicker`'s screen-by-screen
    rollout (Data Management and Dev Board keep `SymbolPickerOverlay` for
    now — see the epic's README for the order). Owns the one piece of wiring
    the standalone component cannot own itself (`SymbolPicker/NOTES.md`):
    what a *choice* means for this screen. Mirrors `CapitalDialogWidget`'s
    shape — the screen ViewModel write happens here, in the composition
    root, not pushed down into the source adapter or up into
    `BackTestModalsHost`.
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
        self._widget_vm = SymbolPickerVM(self._source)
        super().__init__(self._widget_vm, parent=parent)

        self.symbolChosen.connect(self._on_symbol_chosen)

    def set_preferences(self, preferences: SymbolPreferences) -> None:
        """`BackTestModalsHost.set_symbol_preferences`'s seam — forwarded to
        the source adapter, which holds the only reference that matters."""
        self._preferences = preferences
        self._source.set_preferences(preferences)

    def open_dialog(self) -> None:
        self.show()
        self.raise_()

    def refresh(self) -> None:
        """Re-reads `symbolOptions` and re-renders while open. Public so
        `BackTestModalsHost` can call it when the exchange's symbol list
        arrives asynchronously after the dialog was already built (BOT-102) —
        mirrors the old `SymbolPickerOverlay.refresh()`."""
        self._widget_vm.refresh()

    def _on_symbol_chosen(self, symbol: str) -> None:
        self._vm.selectedSymbol = symbol
        # Not part of `ISymbolPickerSource` (recents are host-driven, no
        # picker-side write path per `SymbolPicker/NOTES.md`) — this is the
        # one call the old `SymbolPreferences.bind_picker` made outside the
        # picker's own contract, replicated here so "Gần đây" keeps updating.
        self._preferences.note_used(symbol)
