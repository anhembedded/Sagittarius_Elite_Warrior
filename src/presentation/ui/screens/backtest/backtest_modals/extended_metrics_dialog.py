"""Backtest extended-metrics readout — `EPIC-015` §4c: body is `StatGrid`."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.qml import QmlOverlay
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.StatGrid.stat_grid_vm import (
    StatGridVM,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel

_QML = Path(__file__).resolve().parents[3] / "qml" / "StatGrid" / "StatGrid.qml"


class ExtendedMetricsDialog(QmlOverlay):
    """
    @brief A full readout of a finished run's stats. Chrome is `Overlay`,
    body is `StatGrid.qml`, data is `StatGridVM`.
    """

    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        self._vm = view_model
        self._widget_vm = StatGridVM(get_cards=lambda: view_model.extendedStatCards)
        super().__init__(
            "CHỈ SỐ CHI TIẾT BACKTEST",
            qml_file=_QML,
            context={"vm": self._widget_vm},
            parent=parent,
        )
        self.setObjectName("extendedMetricsPopup")
        self.resize(480, 606)
        view_model.statCardsChanged.connect(self._widget_vm.refresh)

    def showEvent(self, event) -> None:
        self._widget_vm.refresh()
        super().showEvent(event)
