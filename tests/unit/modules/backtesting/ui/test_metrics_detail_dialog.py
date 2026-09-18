"""`MetricsDetailDialogWidget` against a real `BackTestViewModel`.

`EPIC-015` Phase 3 built this as a composition root over
`MetricsDetailPanel.qml`/`MetricsDetailVM`; `EPIC-025` PR 4.3j deleted both and
this file's five promises are restated one for one against the `QTreeWidget`
that replaced them. What only a test building the real composition root can
prove has not changed: that `BacktestMetricsDetailSource` really reads
`extended_metrics_snapshot()`/`selectedTimeframe`, that a `statCardsChanged`
emission refreshes an already-open dialog, and that the "no run yet" state
renders instead of crashing.

The rules those values pass through — grouping, verdicts, the bar's
arithmetic, the clipboard text — are
`logic/test_metrics_detail_rules.py`'s, with no dialog in sight.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QPushButton
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_modals import (
    MetricsDetailDialogWidget,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.extended_metrics_snapshot import (
    ExtendedMetricsSnapshot,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    StatCardData,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone

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
    vm.run_result.set_extended_metrics_snapshot(_snapshot())
    return vm


def test_opening_the_dialog_renders_the_real_view_models_snapshot(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.objectName() == "backtestMetricsDetailDialog"
    assert dialog.isVisible() is True
    assert dialog._profit_label.text() == "+1,148.19"
    assert dialog._loss_label.text() == "-9,341.72"
    dialog.close()


def test_timeframe_seconds_reads_the_view_models_live_selected_timeframe(
    qapp, view_model
):
    """1h = 3600s bars -> `Max Drawdown Duration` (in the fixture's card
    list below) would convert differently than the 60s default — proving
    this reads `selectedTimeframe` live, not a retained/default value."""
    view_model.run_result.set_extended_metrics_snapshot(
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
        for group in dialog._groups
        for row in group.rows
        if row.title == "MAX DRAWDOWN DURATION"
    )
    # 24 bars * 3600s / 86400 = 1 day exactly.
    assert row.info == "≈ 1 days"
    dialog.close()


def test_stat_cards_changed_refreshes_an_already_open_dialog(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    view_model.run_result.set_extended_metrics_snapshot(_snapshot(gross_profit=5000.0))
    view_model.run_result.statCardsChanged.emit()
    qapp.processEvents()

    assert dialog._profit_label.text() == "+5,000.00"
    dialog.close()


def test_no_run_yet_renders_the_empty_snapshot_without_crashing(qapp):
    vm = BackTestViewModel()
    dialog = MetricsDetailDialogWidget(vm)
    dialog.open_dialog()
    qapp.processEvents()

    assert dialog.isVisible() is True
    assert dialog._groups == ()
    assert dialog._tree.topLevelItemCount() == 0
    dialog.close()


def test_the_close_button_closes_the_dialog(qapp, view_model):
    """`EPIC-015` had this as the `.qml` shell's own × re-emitted through the
    ViewModel; it is `Overlay` chrome now, and the promise is the same."""
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.findChild(QPushButton, "btnCloseMetrics").click()
    qapp.processEvents()

    assert not dialog.isVisible()


def test_the_metrics_land_in_the_tree_under_their_section(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    headings = [
        dialog._tree.topLevelItem(index).text(0)
        for index in range(dialog._tree.topLevelItemCount())
    ]
    assert headings == ["PROFIT & LOSS"]
    section = dialog._tree.topLevelItem(0)
    assert [section.child(i).text(0) for i in range(section.childCount())] == [
        "GROSS PROFIT",
        "GROSS LOSS",
    ]
    assert section.child(0).text(1) == "1,148.19 USD"
    dialog.close()


def test_copy_all_puts_the_whole_readout_on_the_clipboard(qapp, view_model):
    dialog = MetricsDetailDialogWidget(view_model)
    dialog.open_dialog()
    qapp.processEvents()

    dialog.findChild(QPushButton, "btnCopyMetrics").click()
    qapp.processEvents()

    text = QGuiApplication.clipboard().text()
    assert "BACKTEST DETAIL METRICS" in text
    assert "GROSS PROFIT: 1,148.19 USD" in text
    assert "891 closed trades" in text
    dialog.close()
