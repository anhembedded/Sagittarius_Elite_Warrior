"""EPIC-005E3: `GapInspectorModal.qml` -> `GapInspectorDialog` (QtWidgets).

Per EPIC-005E's own risk note (this screen touches real trading data): a test
must assert displayed data matches the source data, not just that the dialog
opens.
"""

from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def database_screen(qapp, request):
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()
    container = Mock()

    def resolve_mock(interface):
        from sagittarius_engine.extensions.pyside_mvc.base_view import (
            DEV_MODE_CONFIG_KEY,
        )
        from sagittarius_engine.interfaces.i_config import IConfig
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            mock_config = Mock()
            mock_config.get_all.return_value = {}
            mock_config.get.side_effect = lambda key, default=None: (
                True if key == DEV_MODE_CONFIG_KEY else default
            )
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    view = DataManagementView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    presenter = DataManagementPresenter(view, container)
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return view, presenter


_GAPS = [
    {
        "gap_id": 1,
        "start_time": "2024-01-01 00:00",
        "end_time": "2024-01-01 02:00",
        "fetch_start_time": "2024-01-01T00:00:00",
        "fetch_end_time": "2024-01-01T02:00:00",
        "duration_text": "2h",
        "missing_candles": 120,
    },
    {
        "gap_id": 2,
        "start_time": "2024-02-01 00:00",
        "end_time": "2024-02-01 00:30",
        "fetch_start_time": "2024-02-01T00:00:00",
        "fetch_end_time": "2024-02-01T00:30:00",
        "duration_text": "30m",
        "missing_candles": 30,
    },
]
_SEGMENTS = [
    {
        "is_gap": False,
        "start_time": "a",
        "end_time": "b",
        "ratio": 0.6,
        "candle_count": 1000,
    },
    {
        "is_gap": True,
        "start_time": "b",
        "end_time": "c",
        "ratio": 0.1,
        "candle_count": 120,
    },
]


def test_inspect_gaps_opens_dialog_and_rows_match_source_data(qapp, database_screen):
    view, presenter = database_screen
    view_model = presenter._view_model

    view_model.set_gap_inspector_data("BTCUSDT", "1m", 2, 150, 92.5, _GAPS, _SEGMENTS)
    qapp.processEvents()

    dialog = view._gap_inspector
    assert dialog is not None
    assert dialog.isVisible() is True
    assert dialog.objectName() == "gapInspectorModal"

    assert dialog._subtitle_label.text() == "BTCUSDT (1m) • 2 gaps detected"
    assert dialog._coverage_pct_label.text() == "Độ phủ: 92.5%"
    assert dialog._total_missing_label.text() == "Tổng số nến bị thiếu: 150 nến"
    assert len(dialog._row_widgets) == 2
    assert dialog._row_widgets[0]._repair_button.objectName() == "btnRepairGap_0"
    assert dialog._row_widgets[1]._repair_button.objectName() == "btnRepairGap_1"


def test_repair_gap_click_emits_the_source_gaps_fetch_window(qapp, database_screen):
    view, presenter = database_screen
    view_model = presenter._view_model
    view_model.set_gap_inspector_data("BTCUSDT", "1m", 2, 150, 92.5, _GAPS, _SEGMENTS)
    qapp.processEvents()
    dialog = view._gap_inspector

    captured = []
    view_model.repairGapRequested.connect(
        lambda s, i, start, end: captured.append((s, i, start, end))
    )
    dialog._row_widgets[1]._repair_button.click()
    qapp.processEvents()

    assert captured == [("BTCUSDT", "1m", "2024-02-01T00:00:00", "2024-02-01T00:30:00")]


def test_repair_buttons_disabled_outside_idle_mode(qapp, database_screen):
    view, presenter = database_screen
    view_model = presenter._view_model
    view_model.set_gap_inspector_data("BTCUSDT", "1m", 2, 150, 92.5, _GAPS, _SEGMENTS)
    qapp.processEvents()
    dialog = view._gap_inspector

    assert dialog._btn_repair_all.isEnabled() is True
    assert dialog._row_widgets[0]._repair_button.isEnabled() is True

    view_model.set_ui_mode(UIMode.SYNCING.value)
    qapp.processEvents()

    assert dialog._btn_repair_all.isEnabled() is False
    assert dialog._row_widgets[0]._repair_button.isEnabled() is False


def test_zero_gaps_shows_empty_state_and_disables_repair_all(qapp, database_screen):
    view, presenter = database_screen
    view_model = presenter._view_model
    view_model.set_gap_inspector_data("BTCUSDT", "1m", 0, 0, 100.0, [], [])
    qapp.processEvents()

    dialog = view._gap_inspector
    assert dialog._empty_label.isVisible() is True
    assert len(dialog._row_widgets) == 0
    assert dialog._btn_repair_all.isEnabled() is False
