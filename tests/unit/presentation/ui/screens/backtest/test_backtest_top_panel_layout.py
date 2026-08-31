"""Unit tests for BackTestTopPanel layout and metrics visual elements."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

from PySide6.QtWidgets import QApplication
from Sagittarius_Elite_Warrior.src.presentation.ui.assets import Palette
from Sagittarius_Elite_Warrior.src.presentation.ui.kit import Tone
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_top_panel import (
    BackTestTopPanel,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.backtest.backtest_view_model import (
    BackTestViewModel,
)
from sagittarius_engine.extensions.pyside_mvc import get_theme_bridge


def _ensure_theme_bridge(qapp: QApplication) -> None:
    with contextlib.suppress(ValueError):
        get_theme_bridge(Palette.as_ui_dict())


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
            "title": "TỔNG LÃI/LỖ (NET PNL)",
            "value": "-8,193.54",
            "valueTone": Tone.NEGATIVE,
            "suffix": "USD",
            "badgeText": "-81.94%",
            "badgeTone": Tone.NEGATIVE,
        },
        {
            "title": "TỶ LỆ THẮNG (WIN RATE)",
            "value": "10.33%",
            "valueTone": Tone.NEUTRAL,
            "suffix": "",
            "badgeText": "92/891 lệnh",
            "badgeTone": Tone.NEUTRAL,
        },
    ]
    vm.set_stat_cards(primary=primary, extended=[])
    vm.set_result_warning_text("⚠ Phí giao dịch chiếm phần lớn kết quả.")
    panel._sync_all()
    qapp.processEvents()

    assert panel._stat_cards_row.isVisible()
    assert panel._metrics_header.isVisible()
    assert panel._btn_expand_metrics.isVisible()
    assert panel._btn_expand_metrics.text() == "Mở rộng"
    assert panel._result_warning_label.isVisible()
    assert (
        panel._result_warning_label.text() == "⚠ Phí giao dịch chiếm phần lớn kết quả."
    )
    assert not panel._result_box.isVisible()

    # Click expand button
    panel._btn_expand_metrics.click()
    mock_expand.assert_called_once()

    panel.close()
    panel.deleteLater()
