"""Standalone live preview for the MetricsDetailPanel QML component.

Constructs `StatCardData` instances directly, matching the values in the
mockup image, rather than building a full `BacktestResult`/`BacktestMetrics`
just to reach the same 14 numbers.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtQuickWidgets import QQuickWidget
from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_vm import (
    MetricsDetailVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge

_QML_FILE = Path(__file__).with_name("MetricsDetailPanel.qml")

_NEUTRAL = Tone.NEUTRAL

_CARDS = (
    StatCardData("Gross Profit", "1,148.19", _NEUTRAL, "USD", "", _NEUTRAL),
    StatCardData("Gross Loss", "-9,341.72", _NEUTRAL, "USD", "", _NEUTRAL),
    StatCardData("Avg Trade", "-9.20", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Total Closed Trades", "891", _NEUTRAL, "lệnh", "", _NEUTRAL),
    StatCardData("Avg Winning Trade", "12.48", Tone.POSITIVE, "USD", "", _NEUTRAL),
    StatCardData("Avg Losing Trade", "-11.69", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Largest Winning Trade", "124.48", Tone.POSITIVE, "USD", "", _NEUTRAL),
    StatCardData("Largest Losing Trade", "-40.12", Tone.NEGATIVE, "USD", "", _NEUTRAL),
    StatCardData("Sharpe Ratio", "-63.24", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Sortino Ratio", "-84.59", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Calmar Ratio", "-1.22", _NEUTRAL, "", "", _NEUTRAL),
    StatCardData("Max Drawdown Duration", "48368", _NEUTRAL, "bars", "", _NEUTRAL),
    StatCardData("Max Consecutive Wins", "4", Tone.POSITIVE, "lệnh", "", _NEUTRAL),
    StatCardData("Max Consecutive Losses", "46", _NEUTRAL, "lệnh", "", _NEUTRAL),
)


def build_preview() -> QWidget:
    """Builds the panel with the mockup's own example figures, no host."""
    vm = MetricsDetailVM(
        get_cards=lambda: _CARDS,
        get_gross_profit=lambda: 1148.19,
        get_gross_loss=lambda: -9341.72,
        get_profit_factor=lambda: 0.123,
        get_total_closed_trades=lambda: 891,
        get_fee_rate_percent=lambda: 0.1,
        get_timeframe_seconds=lambda: 60,  # 1m, matches the mockup's "≈ 34 ngày"
    )
    vm.refresh()

    quick = QQuickWidget()
    quick.setObjectName("metricsDetailPanelPreview")
    quick.setResizeMode(QQuickWidget.ResizeMode.SizeRootObjectToView)
    quick.rootContext().setContextProperty("vm", vm)
    quick.rootContext().setContextProperty("Theme", get_theme_bridge())
    # QML context properties are borrowed references; retain for the scene
    # lifetime, same reasoning `QmlOverlay.__init__` documents.
    quick._metrics_detail_vm = vm

    quick.setSource(QUrl.fromLocalFile(str(_QML_FILE)))
    if quick.status() is not QQuickWidget.Status.Ready:
        raise RuntimeError(
            f"QML failed to load: {_QML_FILE}\n"
            + "\n".join(error.toString() for error in quick.errors())
        )
    quick.resize(660, 700)
    return quick
