"""Backtest strategy chooser — the shared `PickerOverlay`, wired to this screen.

Same story as `timezone_picker_dialog.py` (`EPIC-025` PR 4.3e): one of the four
`SelectList.qml` hosts, now on `kit.PickerOverlay`. The subtitle line under each
name is `PickerItem.subtitle`, which the list shape renders — nothing here is
special-cased for it.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PickerItem, PickerOverlay

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "SELECT BOT STRATEGY"


class StrategyPickerDialog(PickerOverlay):
    """@brief Which strategy the run uses."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("strategyPickerModal")
        self.resize(440, 320)
        self.selection_changed.connect(self._on_selected)

    def showEvent(self, event) -> None:
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Offers the catalogue's strategies, with the selected one marked."""
        params = self._vm.strategy_params
        self.selected = params.selectedStrategyKey
        self.set_items(
            [
                PickerItem(
                    value=str(option.get("key", "")),
                    label=str(option.get("name", "")) or str(option.get("key", "")),
                    subtitle=f"Key: {option.get('key', '')}",
                )
                for option in params.strategyOptions
            ]
        )

    def _on_selected(self, key: str) -> None:
        self._vm.strategy_params.selectedStrategyKey = key
        self.accept()
