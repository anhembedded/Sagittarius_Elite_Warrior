"""`BOT-205` — the drop-down list that chooses the display time zone.

A choice from a short, fixed list is a drop-down list (MS `ctrl-drop-down-lists`). The offer is
`get_supported_timezones`, the Backtest screen's own, by its short labels so it fits a chart's
header (the full label is the item's tooltip); the selection follows the shared
`DisplayTimezonePreference`, so a choice made on any screen shows on every one. Only a person's
choice (`QComboBox.activated`) writes the preference; following it never does.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QComboBox, QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_preference import (
    DisplayTimezonePreference,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.services.display_timezone_service import (
    get_supported_timezones,
)

_TIP = (
    "The time zone the chart and the tables show times in. Data and runs stay in UTC; "
    "System is this machine's own time."
)


class DisplayTimezoneCombo(QComboBox):
    """@brief Offers the display zones, with the preference's current one selected."""

    def __init__(
        self, preference: DisplayTimezonePreference, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setObjectName("cmbDisplayTimezone")
        self.setToolTip(_TIP)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self._preference = preference
        for option in get_supported_timezones():
            self.addItem(option["shortLabel"], option["id"])
            self.setItemData(
                self.count() - 1, option["label"], Qt.ItemDataRole.ToolTipRole
            )
        self._follow(preference.zone)
        self.destroyed.connect(preference.subscribe(self._follow))
        self.activated.connect(self._on_chosen)

    def _follow(self, zone: str) -> None:
        self.setCurrentIndex(self.findData(zone))

    def _on_chosen(self, index: int) -> None:
        zone = self.itemData(index)
        if isinstance(zone, str):
            self._preference.set_zone(zone)
