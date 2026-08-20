from __future__ import annotations

import os
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    CoverageSegmentDTO,
    DataGapDTO,
    GetDatabaseGapsResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture
def mock_thread_mgr():
    return Mock()


@pytest.fixture
def mock_dispatcher():
    return Mock()


@pytest.fixture
def mock_container(mock_thread_mgr, mock_dispatcher):
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
    return container


@pytest.fixture
def presenter(qapp, mock_container, request):
    view = DataManagementView()
    view.resize(1400, 800)
    view.show()
    qapp.processEvents()
    request.addfinalizer(view.deleteLater)
    return DataManagementPresenter(view, mock_container)


@pytest.fixture
def view_model(presenter):
    return presenter._view_model


def test_on_inspect_gaps_submits_background_runner(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestInspectGaps("BTCUSDT", "5m")

    mock_thread_mgr.submit.assert_called_with(
        presenter._run_inspect_gaps, "BTCUSDT", "5m"
    )


def test_run_inspect_gaps_dispatches_query_and_populates_view_model(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = GetDatabaseGapsResult(
        symbol="BTCUSDT",
        interval="5m",
        gaps=[
            DataGapDTO(
                gap_id=1,
                symbol="BTCUSDT",
                interval="5m",
                start_time="2024-01-01 00:00:00",
                end_time="2024-01-01 02:00:00",
                fetch_start_time="2024-01-01 00:05:00",
                fetch_end_time="2024-01-01 01:55:00",
                duration_text="2.0h",
                missing_candles=24,
            )
        ],
        total_missing_candles=24,
        total_gaps=1,
        coverage_percentage=95.5,
        coverage_segments=[
            CoverageSegmentDTO(
                is_gap=False,
                start_time="2024-01-01 00:00",
                end_time="2024-01-01 00:00",
                ratio=0.5,
                candle_count=100,
            ),
            CoverageSegmentDTO(
                is_gap=True,
                start_time="2024-01-01 00:00",
                end_time="2024-01-01 02:00",
                ratio=0.5,
                candle_count=24,
            ),
        ],
    )

    presenter._run_inspect_gaps("BTCUSDT", "5m")

    assert view_model.gapInspectorSymbol == "BTCUSDT"
    assert view_model.gapInspectorInterval == "5m"
    assert view_model.gapInspectorTotalGaps == 1
    assert view_model.gapInspectorTotalMissing == 24
    assert len(view_model.gapList) == 1
    assert len(view_model.coverageSegments) == 2


def test_on_repair_gap_submits_worker(presenter, view_model, mock_thread_mgr):
    view_model.requestRepairGap(
        "BTCUSDT", "1m", "2024-01-01 00:01:00", "2024-01-01 01:00:00"
    )

    assert presenter.fsm.current_state == UIMode.SYNCING
    mock_thread_mgr.submit.assert_called_with(
        presenter._run_repair_gap,
        "BTCUSDT",
        "1m",
        "2024-01-01 00:01:00",
        "2024-01-01 01:00:00",
    )


def test_run_repair_gap_dispatches_command(presenter, view_model, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = RepairDataGapResult(
        success=True, repaired_candles=60, message="Đã vá thành công 60 nến."
    )

    presenter.fsm.transition_to(UIMode.SYNCING)
    presenter._run_repair_gap(
        "BTCUSDT", "1m", "2024-01-01 00:01:00", "2024-01-01 01:00:00"
    )

    assert any(
        call.args[0] is RepairDataGapCommand
        for call in mock_dispatcher.dispatch.call_args_list
    )
    assert presenter.fsm.current_state == UIMode.IDLE
