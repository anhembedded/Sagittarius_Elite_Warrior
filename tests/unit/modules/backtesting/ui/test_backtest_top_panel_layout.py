"""Unit tests for BackTestTopPanel layout and metrics visual elements."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_top_panel import (
    BackTestTopPanel,
)
from Sagittarius_Elite_Warrior.src.modules.backtesting.ui.backtest_view_model import (
    BackTestViewModel,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.kit import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.theme_bootstrap import (
    seed_app_theme,
)


def _ensure_theme_bridge(qapp: QApplication) -> None:
    """One entry point (`BOT-133`), and the `suppress` is load-bearing.

    `get_theme_bridge()` inside `seed_app_theme()` is a first-caller-wins
    singleton that raises `ValueError` when a second caller offers a different
    palette — which happens whenever this file runs in the same process as a
    suite that seeded a placeholder one (`kit/conftest.py` does, deliberately).
    Either palette is fine for the layout assertions below; what matters is
    that *some* theme exists before the panel is built.
    """
    with contextlib.suppress(ValueError):
        seed_app_theme()


def test_top_panel_initial_state_shows_result_box(qapp: QApplication) -> None:
    _ensure_theme_bridge(qapp)
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
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()

    mock_expand = MagicMock()
    vm.openExtendedMetricsRequested.connect(mock_expand)

    primary = [
        {
            "title": "TOTAL PNL (NET PNL)",
            "value": "-8,193.54",
            "valueTone": Tone.NEGATIVE,
            "suffix": "USD",
            "badgeText": "-81.94%",
            "badgeTone": Tone.NEGATIVE,
        },
        {
            "title": "WIN RATE",
            "value": "10.33%",
            "valueTone": Tone.NEUTRAL,
            "suffix": "",
            "badgeText": "92/891 trades",
            "badgeTone": Tone.NEUTRAL,
        },
    ]
    vm.run_result.set_stat_cards(primary=primary, extended=[])
    vm.run_result.set_result_warning_text("⚠ Trading fees make up most of the result.")
    panel._sync_all()
    qapp.processEvents()

    assert panel._stat_cards_row.isVisible()
    assert panel._metrics_header.isVisible()
    assert panel._btn_expand_metrics.isVisible()
    assert panel._btn_expand_metrics.text() == "Expand"
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


def test_top_panel_save_report_button_enables_only_once_cards_exist(
    qapp: QApplication,
) -> None:
    """`BOT-115B` — "Save report" starts disabled (no run yet) and enables
    the moment stat cards appear, mirroring the header/warning visibility
    `_sync_metrics_header` already drives from the same `has_cards` flag."""
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert not panel._btn_save_report.isEnabled()

    mock_export = MagicMock()
    vm.exportReportRequested.connect(mock_export)

    vm.run_result.set_stat_cards(
        primary=[
            {
                "title": "WIN RATE",
                "value": "10.33%",
                "valueTone": Tone.NEUTRAL,
                "suffix": "",
                "badgeText": "92/891 trades",
                "badgeTone": Tone.NEUTRAL,
            }
        ],
        extended=[],
    )
    panel._sync_all()
    qapp.processEvents()

    assert panel._btn_save_report.isEnabled()

    panel._btn_save_report.click()
    mock_export.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_import_report_button_emits_the_request_signal(
    qapp: QApplication,
) -> None:
    """`BOT-115C` — "Import report" is always available (no result needs to
    exist first, unlike "Save report")."""
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert panel._btn_import_report.isEnabled()

    mock_import = MagicMock()
    vm.importReportRequested.connect(mock_import)

    panel._btn_import_report.click()

    mock_import.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_compare_reports_button_emits_the_request_signal(
    qapp: QApplication,
) -> None:
    """`BOT-115D` — "Compare reports" is always available, same reasoning
    as "Import report": the comparison dialog's own Column A shows "run a
    backtest first" until a result exists, rather than the button being
    disabled and unexplained."""
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert panel._btn_compare_reports.isEnabled()

    mock_compare = MagicMock()
    vm.openCompareReportsRequested.connect(mock_compare)

    panel._btn_compare_reports.click()

    mock_compare.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_out_of_sample_comparison_button_emits_the_request_signal(
    qapp: QApplication,
) -> None:
    """`BOT-107A` — same "always available" reasoning as "Compare reports":
    the dialog itself shows a "not computed for this run" message until an
    out-of-sample-validated result exists."""
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert panel._btn_out_of_sample_comparison.isEnabled()

    mock_open = MagicMock()
    vm.openOutOfSampleComparisonRequested.connect(mock_open)

    panel._btn_out_of_sample_comparison.click()

    mock_open.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_monte_carlo_button_emits_the_request_signal(
    qapp: QApplication,
) -> None:
    """`BOT-107B` — same "always available" reasoning as its siblings: the
    dialog itself shows "run a backtest first"/"too few trades" until a
    real, reshufflable result exists."""
    _ensure_theme_bridge(qapp)
    vm = BackTestViewModel()
    panel = BackTestTopPanel(vm)
    panel.resize(1200, 350)
    panel.show()
    qapp.processEvents()

    assert panel._btn_monte_carlo.isEnabled()

    mock_open = MagicMock()
    vm.openMonteCarloRequested.connect(mock_open)

    panel._btn_monte_carlo.click()

    mock_open.assert_called_once()

    panel.close()
    panel.deleteLater()


def test_top_panel_imported_report_banner_shows_only_while_viewing(
    qapp: QApplication,
) -> None:
    """`BOT-115C` — the banner is visible only in `VIEWING_IMPORTED_REPORT`
    with real text, and its action emits the exit-view request."""
    _ensure_theme_bridge(qapp)
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
    assert panel._imported_report_banner.message == (
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
    _ensure_theme_bridge(qapp)
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
    _ensure_theme_bridge(qapp)
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
    _ensure_theme_bridge(qapp)
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
