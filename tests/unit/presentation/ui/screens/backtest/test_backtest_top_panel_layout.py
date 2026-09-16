"""Unit tests for BackTestTopPanel layout and metrics visual elements."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_top_panel import (
    BackTestTopPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
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
