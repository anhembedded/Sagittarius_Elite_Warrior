"""`EPIC-015` Phase 3: `MetricsDetailDialogWidget`, Backtest's composition
root for `MetricsDetailPanel.qml`/`MetricsDetailVM`, rendered for real
against a real `BackTestViewModel`.

Complements `test_metrics_detail_modal_host.py` (the screen-agnostic
`MetricsDetailModal` host, exercised with a hand-built `MetricsDetailVM`) —
what only a test building the real composition root can prove is this app's
own wiring: `BacktestMetricsDetailSource` actually reads
`BackTestViewModel.extended_metrics_snapshot()`/`selectedTimeframe`, a
`statCardsChanged` emission refreshes the already-open dialog, and the
"no run yet" (`None` snapshot) state renders without crashing.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.performance_metrics_view import (
    StatCardData,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_modals import (
    MetricsDetailDialogWidget,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)

_NEUTRAL = Tone.NEUTRAL


def _snapshot(**overrides: object) -> ExtendedMetricsSnapshot:
    defaults: dict[str, object] = {
        "cards": (
            StatCardData("Gross Profit", "1,148.19", _NEUTRAL, "USD", "", _NEUTRAL),
            StatCardData("Gross Loss", "-9,341.72", _NEUTRAL, "USD", "", _NEUTRAL),
        ),
        "gross_profit": 1148.19,
        "gross_loss": -9341.72,
        "profit_factor": 0.123,
        "total_closed_trades": 891,
        "fee_rate_percent": 0.1,
    }
    defaults.update(overrides)
    return ExtendedMetricsSnapshot(**defaults)  # type: ignore[arg-type]


@pytest.fixture
def view_model():
    vm = BackTestViewModel()
    vm.selectedTimeframe = "1h"
    vm.set_extended_metrics_snapshot(_snapshot())
    return vm


def test_opening_the_dialog_renders_the_real_view_models_snapshot(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.objectName() == "backtestMetricsDetailDialog"
    assert dialog.isVisible() is True
    label = dialog.root_object.findChild(QObject, "lblGrossProfit")
    assert label.property("text") == "+1,148.19"
    dialog.close()


def test_timeframe_seconds_reads_the_view_models_live_selected_timeframe(
    qapp, view_model
):
    """1h = 3600s bars -> `Max Drawdown Duration` (in the fixture's card
    list below) would convert differently than the 60s default — proving
    this reads `selectedTimeframe` live, not a retained/default value."""
    view_model.set_extended_metrics_snapshot(
        _snapshot(
            cards=(
                StatCardData(
                    "Max Drawdown Duration", "24", _NEUTRAL, "bars", "", _NEUTRAL
                ),
            )
        )
    )
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    row = next(
        row
        for group in dialog._widget_vm.groups
        for row in group["rows"]
        if row["title"] == "MAX DRAWDOWN DURATION"
    )
    # 24 bars * 3600s / 86400 = 1 day exactly.
    assert row["infoBadge"] == "≈ 1 ngày"
    dialog.close()


def test_stat_cards_changed_refreshes_an_already_open_dialog(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    view_model.set_extended_metrics_snapshot(_snapshot(gross_profit=5000.0))
    view_model.statCardsChanged.emit()
    qapp.processEvents()

    label = dialog.root_object.findChild(QObject, "lblGrossProfit")
    assert label.property("text") == "+5,000.00"
    dialog.close()


def test_no_run_yet_renders_the_empty_snapshot_without_crashing(qapp):
    vm = BackTestViewModel()
    dialog = MetricsDetailDialogWidget(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.isVisible() is True
    assert dialog._widget_vm.groups == []
    dialog.close()


def test_closing_via_the_dialog_shell_x_closes_the_outer_dialog(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    button = dialog.root_object.findChild(QObject, "btnDialogShellClose")
    assert button is not None
    dialog._widget_vm.requestClose()
    qapp.processEvents()

    assert not dialog.isVisible()
