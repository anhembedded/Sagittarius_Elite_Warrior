"""Unit tests for BackTestTopPanel layout and metrics visual elements."""

from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication, QLabel, QWidget
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_top_panel import (
    BackTestTopPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.logic.performance_metrics_view import (
    StatCardData,
    stat_cards_to_qml,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind


def test_top_panel_initial_state_shows_result_box(qapp: QApplication) -> None:
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert not panel._stat_cards_row.isVisible()
    assert not panel._metrics_header.isVisible()
    assert not panel._result_warning_label.isVisible()
    assert panel._result_box.isVisible()

    panel.close()
    panel.deleteLater()


def test_top_panel_with_cards_shows_header_cards_and_expand_button(
    qapp: QApplication,
) -> None:
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()

    mock_expand = MagicMock()
    vm.openExtendedMetricsRequested.connect(mock_expand)

    primary = stat_cards_to_qml(
        [
            StatCardData(
                "net_pnl",
                "TOTAL PNL (NET PNL)",
                -8193.54,
                ColumnKind.MONEY,
                Tone.NEGATIVE,
                "USD",
                "Net PnL (%)",
                -81.94,
                ColumnKind.PERCENT,
                Tone.NEGATIVE,
            ),
            StatCardData(
                "win_rate",
                "WIN RATE",
                10.33,
                ColumnKind.PERCENT,
                Tone.NEUTRAL,
                "",
                "Winning / closed trades",
                "92 / 891",
            ),
        ]
    )
    vm.run_result.set_stat_cards(primary=primary, extended=[])
    vm.run_result.set_result_warning_text("⚠ Trading fees make up most of the result.")
    panel._sync_all()
    qapp.processEvents()

    assert panel._stat_cards_row.isVisible()
    assert panel._metrics_header.isVisible()
    assert panel._btn_expand_metrics.isVisible()
    assert panel._btn_expand_metrics.text() == "Details"
    assert panel._result_warning_label.isVisible()
    assert (
        panel._result_warning_label.text()
        == "⚠ Trading fees make up most of the result."
    )
    assert not panel._result_box.isVisible()

    # Click expand button
    panel._btn_expand_metrics.click()
    mock_expand.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_imported_report_banner_shows_only_while_viewing(
    qapp: QApplication,
) -> None:
    """`BOT-115C` — the banner is visible only in `VIEWING_IMPORTED_REPORT`
    with real text, and its action emits the exit-view request."""
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert not panel._imported_report_banner.isVisible()

    vm.importedReportBannerText = "Viewing imported report — run.sagi-report.json"
    vm.set_ui_mode("VIEWING_IMPORTED_REPORT")
    qapp.processEvents()

    assert panel._imported_report_banner.isVisible()
    assert panel._imported_report_banner.text == (
        "Viewing imported report — run.sagi-report.json"
    )

    mock_exit = MagicMock()
    vm.exitImportedReportViewRequested.connect(mock_exit)
    panel._imported_report_banner.action_button.click()
    mock_exit.assert_called_once()

    vm.set_ui_mode("IDLE")
    qapp.processEvents()

    assert not panel._imported_report_banner.isVisible()

    panel.close()
    panel.deleteLater()


def test_session_run_history_combo_starts_disabled_with_only_the_placeholder(
    qapp: QApplication,
) -> None:
    """`BOT-095G` — nothing has run yet, so there is nothing to redisplay."""
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert not panel._combo_run_history.isEnabled()
    assert panel._combo_run_history.count() == 1

    panel.close()
    panel.deleteLater()


def test_session_run_history_combo_populates_and_selecting_an_entry_requests_restore(
    qapp: QApplication,
) -> None:
    """`BOT-095G` — the dropdown mirrors `vm.sessionRunHistory` and picking
    a real entry asks the Presenter (via `requestRestoreRun`) to redisplay
    that run's `run_id`. A real Qt signal connection, not a mock standing
    in for it: breaking the `currentIndexChanged.connect(...)` line in
    `backtest_top_panel.py` makes this test fail."""
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    mock_restore = MagicMock()
    vm.restoreRunRequested.connect(mock_restore)

    vm.set_session_run_history(
        [
            {"run_id": "run-2", "label": "15:20:05 — ETHUSDT | 5m — +28.4%"},
            {"run_id": "run-1", "label": "15:19:00 — ETHUSDT | 1m — -3.2%"},
        ]
    )
    panel._sync_all()
    qapp.processEvents()

    combo = panel._combo_run_history
    assert combo.isEnabled()
    assert combo.count() == 3
    assert combo.currentIndex() == 0

    combo.setCurrentIndex(1)

    mock_restore.assert_called_once_with("run-2")

    panel.close()
    panel.deleteLater()


def test_session_run_history_combo_resets_to_placeholder_on_refresh(
    qapp: QApplication,
) -> None:
    """A refresh (a new run pushed, or the oldest slot evicted) must not
    leave a stale selection highlighted — `vm.sessionRunHistory` no longer
    describes "the run picked last time" as the thing currently on screen."""
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    vm.set_session_run_history([{"run_id": "run-1", "label": "run one"}])
    panel._sync_all()
    panel._combo_run_history.setCurrentIndex(1)
    assert panel._combo_run_history.currentIndex() == 1

    vm.set_session_run_history(
        [
            {"run_id": "run-2", "label": "run two"},
            {"run_id": "run-1", "label": "run one"},
        ]
    )
    panel._sync_all()
    qapp.processEvents()

    assert panel._combo_run_history.currentIndex() == 0

    panel.close()
    panel.deleteLater()


def test_a_failed_run_shows_as_an_error_notice(qapp: QApplication) -> None:
    """`EPIC-033L` stage 4: a failure is the platform's error icon and its
    words, not red text alone."""
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.show()

    vm.run_result.set_result("Sync failed: timeout", is_error=True)
    qapp.processEvents()

    assert panel._result_error.isVisible()
    assert panel._result_error.text == "Sync failed: timeout"
    assert not panel._result_text.isVisible()

    vm.run_result.set_result("Running...", is_error=False)
    qapp.processEvents()

    assert not panel._result_error.isVisible()
    assert panel._result_text.toPlainText() == "Running..."
    panel.close()
    panel.deleteLater()


def test_the_panel_has_no_style_sheet_and_no_second_heading(
    qapp: QApplication,
) -> None:
    """A dock's content is its controls (`ui-presentation-rule.md` §8): no
    card painted inside it, no heading above the dock's own title."""
    panel = BackTestTopPanel(BackTestViewModel())

    styled = [w for w in [panel, *panel.findChildren(QWidget)] if w.styleSheet()]
    assert styled == []
    texts = [label.text() for label in panel.findChildren(QLabel)]
    assert not any("PERFORMANCE METRICS" in text.upper() for text in texts)
