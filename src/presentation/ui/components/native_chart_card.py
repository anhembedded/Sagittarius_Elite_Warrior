"""BOT-098F6D — minimal BaseCard wrapper for the native Backtest chart."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.components.base_card import (
    BaseCard,
)


class NativeChartCard(BaseCard):
    """Gives the native `QQuickWidget` the same header/body layout
    `ChartCard` gets — `BacktestChartControls` and the timeframe toolbar
    stay QtWidgets attached via `add_to_header`, exactly as the BOT-098F6
    architecture contract requires, without native needing to know
    anything about headers itself."""

    def __init__(self, symbol: str, content: QWidget, parent=None) -> None:
        super().__init__(title=f"Live Chart: {symbol}", parent=parent)
        self.body_layout.addWidget(content)
