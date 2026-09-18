"""Backtest timezone chooser — the shared `PickerOverlay`, wired to this screen.

`EPIC-015` §4c made this one of four hosts of `SelectList.qml`; `EPIC-025` PR
4.3e deletes that component (ADR D21) and every one of the four moves onto
`kit.PickerOverlay`, the QtWidgets "pick one from a list" that has existed since
PR 1.6b and already serves the symbol pickers. Nothing was invented here: the
survey found the component, and this file is the four lines of wiring it cannot
own — where the options come from, and what a choice means for this screen.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PickerItem, PickerOverlay

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_TITLE = "SELECT DISPLAY TIME ZONE"
_SUBTITLE = (
    "Only changes the displayed time zone. "
    "Data and backtests are always computed in UTC."
)


class TimezonePickerDialog(PickerOverlay):
    """@brief Which timezone the UI displays."""

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        super().__init__(_TITLE, _SUBTITLE, searchable=True, parent=parent)
        self.setObjectName("timezonePickerModal")
        self.resize(440, 350)
        self.selection_changed.connect(self._on_selected)

    def showEvent(self, event) -> None:
        """Re-reads on every open — the current timezone changes between them,
        and the dialog is built once and reused."""
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """Offers the supported timezones, with the current one marked."""
        self.selected = self._vm.time_range.displayTimezone
        self.set_items(
            [
                PickerItem(
                    value=str(option.get("id", "")),
                    label=str(option.get("label", "")) or str(option.get("id", "")),
                )
                for option in self._vm.time_range.displayTimezoneOptions
            ]
        )

    def _on_selected(self, timezone_id: str) -> None:
        self._vm.setDisplayTimezone(timezone_id)
        self.accept()
