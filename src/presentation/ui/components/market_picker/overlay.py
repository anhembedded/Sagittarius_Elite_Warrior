"""`MarketPickerDialog` — choose Spot vs Futures. Shared by every screen.

Body is the shared `SelectList.qml`; options come from `MARKET_OPTIONS`
(`catalogue.py`), not from a screen ViewModel — every screen offers the
same three markets, so there is nothing for a screen to narrow (unlike
`qml/TimeframePicker/timeframe_vm.py`'s `TimeframeVM`, which takes
`get_codes` for exactly that reason).

Callback-constructed rather than hardwired to one screen's ViewModel
(unlike `StrategyPickerDialog`, which takes `BackTestViewModel` directly)
precisely because this is meant to serve more than one screen (Backtest,
Dev Board — user decision 2026-08-29, "tạm thời nó là common") without
either depending on the other's ViewModel shape.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.SelectList.select_list_vm import (
    SelectListVM,
)

from .catalogue import MARKET_OPTIONS

_TITLE = "CHỌN THỊ TRƯỜNG"
_QML = Path(__file__).resolve().parents[2] / "qml" / "SelectList" / "SelectList.qml"


class MarketPickerDialog(QmlOverlay):
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
        self._widget_vm = SelectListVM(
            get_options=lambda: MARKET_OPTIONS,
            get_current=get_current,
        )
        super().__init__(
            _TITLE,
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("marketPickerModal")
        self.resize(360, 220)
        self._widget_vm.chosen.connect(self._on_selected)

    def showEvent(self, event) -> None:
        """Re-reads the current choice on every open — a screen's selected
        market can change between opens, same reasoning
        `TimeframePickerDialog.open_dialog()` documents."""
        self._widget_vm.refresh()
        super().showEvent(event)

    def _on_selected(self, market_id: str) -> None:
        self.chosen.emit(market_id)
        self.accept()
