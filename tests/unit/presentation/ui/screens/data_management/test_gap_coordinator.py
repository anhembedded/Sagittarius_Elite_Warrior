from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_gaps import (
    CoverageSegmentDTO,
    DataGapDTO,
    GetDatabaseGapsQuery,
    GetDatabaseGapsResult,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    GapCoordinator,
)
from sagittarius_engine.runtime.tasks.cancellation_token import CancellationToken


@pytest.fixture
def gap_fixture():
    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_gap_inspector": Mock(),
        "ui_unlock": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
        "is_shutdown": Mock(return_value=False),
        "on_check_status": Mock(),
    }

    coordinator = GapCoordinator(
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_gap_inspector_signal=signals["ui_gap_inspector"],
        ui_unlock_signal=signals["ui_unlock"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
        is_shutdown_requested=signals["is_shutdown"],
        on_check_status_callback=signals["on_check_status"],
    )

    return coordinator, dispatcher, tracker, signals


def test_gap_coordinator_inspect_gaps_success(gap_fixture):
    coordinator, dispatcher, tracker, signals = gap_fixture

    gap_dto = DataGapDTO(
        gap_id=1,
        symbol="BTCUSDT",
        interval="1m",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 01:00:00",
        fetch_start_time="2024-01-01 00:00:00",
        fetch_end_time="2024-01-01 01:00:00",
        duration_text="1 hour",
        missing_candles=60,
    )
    seg_dto = CoverageSegmentDTO(
        is_gap=False,
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 02:00:00",
        ratio=1.0,
        candle_count=120,
    )
    dispatcher.dispatch.return_value = GetDatabaseGapsResult(
        symbol="BTCUSDT",
        interval="1m",
        total_gaps=1,
        total_missing_candles=60,
        coverage_percentage=95.0,
        gaps=[gap_dto],
        coverage_segments=[seg_dto],
    )

    coordinator.run_inspect_gaps("BTCUSDT", "1m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], GetDatabaseGapsQuery)
    signals["ui_gap_inspector"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_gap_coordinator_repair_gap_success(gap_fixture):
    coordinator, dispatcher, tracker, signals = gap_fixture

    def dispatch_mock(cmd_type, cmd):
        if cmd_type is RepairDataGapCommand:
            return RepairDataGapResult(
                success=True, repaired_candles=60, message="Gap repaired"
            )
        if cmd_type is GetDatabaseGapsQuery:
            return GetDatabaseGapsResult(
                symbol="BTCUSDT",
                interval="1m",
                total_gaps=0,
                total_missing_candles=0,
                coverage_percentage=100.0,
                gaps=[],
                coverage_segments=[],
            )
        return Mock()

    dispatcher.dispatch.side_effect = dispatch_mock

    coordinator.run_repair_gap(
        "BTCUSDT", "1m", "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"
    )

    dispatcher.dispatch.assert_called()
    signals["on_check_status"].assert_called_once_with("BTCUSDT", "1m")
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_gap_coordinator_repair_all_gaps_cancelled(gap_fixture):
    coordinator, dispatcher, tracker, signals = gap_fixture

    gap_dto = DataGapDTO(
        gap_id=1,
        symbol="BTCUSDT",
        interval="1m",
        start_time="2024-01-01 00:00:00",
        end_time="2024-01-01 01:00:00",
        fetch_start_time="2024-01-01T00:00:00Z",
        fetch_end_time="2024-01-01T01:00:00Z",
        duration_text="1 hour",
        missing_candles=60,
    )
    dispatcher.dispatch.return_value = GetDatabaseGapsResult(
        symbol="BTCUSDT",
        interval="1m",
        total_gaps=1,
        total_missing_candles=60,
        coverage_percentage=95.0,
        gaps=[gap_dto],
        coverage_segments=[],
    )

    token = CancellationToken()
    token.cancel()

    coordinator.run_repair_all_gaps("BTCUSDT", "1m", token)

    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.CANCELLED
