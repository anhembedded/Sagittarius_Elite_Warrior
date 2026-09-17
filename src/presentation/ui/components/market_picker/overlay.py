"""`MarketPickerDialog` — choose Spot vs Futures. Shared by every screen.

Options come from `MARKET_OPTIONS` (`catalogue.py`), not from a screen
ViewModel — every screen offers the same three markets, so there is nothing for
a screen to narrow (unlike the timeframe picker, whose `get_codes` exists for
exactly that reason).

Callback-constructed rather than hardwired to one screen's ViewModel (unlike
`StrategyPickerDialog`, which takes `BackTestViewModel` directly) precisely
because this is meant to serve more than one screen (Backtest, Dev Board — user
decision 2026-08-29, *"tạm thời nó là common"*) without either depending on the
other's ViewModel shape.

`EPIC-025` PR 4.3e moved the body from `SelectList.qml` onto `kit.PickerOverlay`
with the rest of that component's four hosts (ADR D21).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import PickerItem, PickerOverlay

from .catalogue import MARKET_OPTIONS

_TITLE = "SELECT MARKET"


class MarketPickerDialog(PickerOverlay):
    """
    @brief A modal, single-column list of markets. Choosing emits `chosen`
    and closes.
    """

    chosen = Signal(str)

    def __init__(
        self,
        get_current: Callable[[], str],
        parent: QWidget | None = None,
    ) -> None:
        self._get_current = get_current
        super().__init__(_TITLE, parent=parent)
        self.setObjectName("marketPickerModal")
        self.resize(360, 220)
        self.selection_changed.connect(self._on_selected)

    def showEvent(self, event) -> None:
        """Re-reads the current choice on every open — a screen's selected
        market can change between opens, same reasoning
        `TimeframePickerDialog.open_dialog()` documents."""
        self.refresh()
        super().showEvent(event)

    def refresh(self) -> None:
        """The catalogue's markets, with the caller's current one marked."""
        self.selected = self._get_current()
        self.set_items(
            [
                PickerItem(value=option["id"], label=option["label"])
                for option in MARKET_OPTIONS
            ]
        )

    def _on_selected(self, market_id: str) -> None:
        self.chosen.emit(market_id)
        self.accept()
