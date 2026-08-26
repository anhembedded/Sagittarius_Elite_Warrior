"""Backtest extended-metrics readout."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QScrollArea,
    QWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import (
    Overlay,
    StatCard,
    Tone,
)

if TYPE_CHECKING:
    from ..backtest_view_model import BackTestViewModel


class ExtendedMetricsDialog(Overlay):
    def __init__(
        self, view_model: BackTestViewModel, parent: QWidget | None = None
    ) -> None:
        super().__init__("CHỈ SỐ CHI TIẾT BACKTEST", parent=parent)
        self.setObjectName("extendedMetricsPopup")
        self._vm = view_model
        self.resize(480, 606)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        self._grid = QGridLayout(content)
        self._grid.setSpacing(12)
        scroll.setWidget(content)
        self.body_layout.addWidget(scroll)

        view_model.statCardsChanged.connect(self._sync)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._sync()

    def _sync(self) -> None:
        while self._grid.count():
            item = self._grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for index, card_data in enumerate(self._vm.extendedStatCards):
            card = StatCard(card_data.get("title", "").upper())
            card.setObjectName(f"cardExtendedMetric_{index}")
            # This row is a raw data dump, not a verdict, so the tone the
            # builder computed is used as-is rather than being forced
            # neutral here — "Total Fees Paid" is deliberately not neutral
            # when fees dominate (BOT-079).
            card.set_value(
                card_data.get("value", ""),
                tone=card_data.get("valueTone", Tone.NEUTRAL),
            )
            card.set_suffix(card_data.get("suffix", ""))
            self._grid.addWidget(card, index // 2, index % 2)
