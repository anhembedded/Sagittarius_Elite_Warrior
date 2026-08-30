"""`EPIC-015` Phase 3: `MetricsDetailPanel.qml`'s generic `QDialog` host,
rendered for real.

Thin on purpose (`qml-rule.md` §7): `MetricsDetailVM`'s own rules already
have full coverage with no `QApplication` at all
(`qml/MetricsDetailPanel/tests/test_metrics_detail_vm.py`), and the
standalone `.qml`'s render/interaction behaviour is already covered with no
host at all (`qml/MetricsDetailPanel/tests/test_metrics_detail_qml.py`).
What only a test that builds the real `MetricsDetailModal` can prove is this
class's own contribution: it actually opens as a real `QDialog`, the ×/"Đóng"
close path (surfaced as `MetricsDetailVM.closeRequested`) closes the outer
shell, "Copy tất cả" actually reaches the system clipboard, and a broken
`.qml` raises instead of rendering a blank box — the same four things
`test_symbol_picker_modal_host.py` proves for its own host, minus the
inner-`Popup` race that host alone has to handle (`metrics_detail_modal_host.py`'s
own docstring: `DialogShell` has no `Popup` of its own to race against).

Built against a hand-constructed `MetricsDetailVM`, not a real
`BackTestViewModel` — this host is screen-agnostic (`qml-rule.md` §0.2:
`MetricsDetailModal` has no idea Backtest exists). The screen wiring itself
(`BacktestMetricsDetailSource` reading real `BackTestViewModel` data) is
`test_metrics_detail_dialog.py`'s job, not this file's.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QGuiApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_vm import (
    MetricsDetailVM,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.logic.performance_metrics_view import (
    StatCardData,
)

_NEUTRAL = Tone.NEUTRAL

_CARDS = (
    StatCardData("Gross Profit", "1,148.19", _NEUTRAL, "USD", "", _NEUTRAL),
    StatCardData("Sharpe Ratio", "-63.24", _NEUTRAL, "", "", _NEUTRAL),
)


def _vm() -> MetricsDetailVM:
    vm = MetricsDetailVM(
        get_cards=lambda: _CARDS,
        get_gross_profit=lambda: 1148.19,
        get_gross_loss=lambda: -9341.72,
        get_profit_factor=lambda: 0.123,
        get_total_closed_trades=lambda: 891,
        get_fee_rate_percent=lambda: 0.1,
        get_timeframe_seconds=lambda: 60,
    )
    vm.refresh()
    return vm


def test_opening_the_dialog_loads_and_renders_the_groups(qapp):
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_modal_host as host_module

    vm = _vm()
    dialog = host_module.MetricsDetailModal(vm)
    dialog.show()
    qapp.processEvents()

    assert dialog.objectName() == "metricsDetailModal"
    assert dialog.isVisible() is True
    assert dialog.root_object.objectName() == "metricsDetailPanel"
    risk_group = next(g for g in vm.groups if g["label"] == "RỦI RO")
    assert len(risk_group["rows"]) > 0
    dialog.close()


def test_close_requested_closes_the_outer_dialog(qapp):
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_modal_host as host_module

    vm = _vm()
    dialog = host_module.MetricsDetailModal(vm)
    dialog.show()
    qapp.processEvents()

    vm.requestClose()
    qapp.processEvents()

    assert not dialog.isVisible()


def test_copy_all_actually_copies_the_real_text_to_the_clipboard(qapp):
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_modal_host as host_module

    vm = _vm()
    dialog = host_module.MetricsDetailModal(vm)
    dialog.show()
    qapp.processEvents()

    vm.requestCopy()
    qapp.processEvents()

    text = QGuiApplication.clipboard().text()
    assert "GROSS PROFIT" in text
    assert "1,148.19" in text
    assert "SHARPE RATIO" in text
    assert vm.footerText in text
    dialog.close()


def test_a_broken_qml_file_raises_instead_of_rendering_a_blank_box(
    qapp, tmp_path, monkeypatch
):
    """Mirrors `test_symbol_picker_modal_host.py`'s equivalent case: a
    `QQuickWidget` whose source fails to load renders an empty rectangle and
    says nothing. `MetricsDetailModal` must fail loudly instead."""
    import Sagittarius_Elite_Warrior.src.presentation.ui.qml.MetricsDetailPanel.metrics_detail_modal_host as host_module

    broken = tmp_path / "Broken.qml"
    broken.write_text("import QtQuick\nItem { this is not qml }\n")
    monkeypatch.setattr(host_module, "_QML_FILE", broken)

    with pytest.raises(RuntimeError, match="QML failed to load"):
        host_module.MetricsDetailModal(_vm())
