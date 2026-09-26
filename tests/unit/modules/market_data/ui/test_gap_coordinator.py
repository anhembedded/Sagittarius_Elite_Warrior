from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.modules.market_data.application.database.repair_data_gap import (
    RepairDataGapCommand,
    RepairDataGapResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.application.queries.get_database_gaps import (
    CoverageSegmentDTO,
    DataGapDTO,
    GetDatabaseGapsQuery,
    GetDatabaseGapsResult,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.ui.coordinators import (
    DataManagementActionKind,
    GapCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.constants import UIMode
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


# ---------------------------------------------------------------------------
# `request_*` orchestration (BOT-144) — validate/transition/submit, moved
# here from the Presenter's own `_on_repair_gap`/`_on_repair_all_gaps`.
# ---------------------------------------------------------------------------


def test_request_repair_gap_transitions_and_submits_a_fresh_token(gap_fixture):
    coordinator, _dispatcher, _tracker, signals = gap_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_repair_gap("BTCUSDT", "1m", "2024-01-01", "2024-01-02")

    signals["transition_fsm"].assert_called_once_with(UIMode.SYNCING)
    method, symbol, interval, start, end, token = thread_manager.submit.call_args.args
    assert method == coordinator.run_repair_gap
    assert (symbol, interval, start, end) == (
        "BTCUSDT",
        "1m",
        "2024-01-01",
        "2024-01-02",
    )
    assert token is coordinator.cancellation_token


def test_request_repair_gap_does_not_submit_when_the_fsm_refuses(gap_fixture):
    """`-> False` here means "an FSM exists and rejected the move" — the one
    case pre-`BOT-144`'s `if self.fsm and not self.fsm.transition_to(...)`
    bailed on, distinct from "there is no FSM at all" (see
    `DataManagementPresenter._transition_fsm_safe`)."""
    coordinator, _dispatcher, _tracker, signals = gap_fixture
    signals["transition_fsm"].return_value = False

    coordinator.request_repair_gap("BTCUSDT", "1m", "2024-01-01", "2024-01-02")

    coordinator._thread_manager.submit.assert_not_called()


def test_request_repair_gap_does_nothing_once_shutdown(gap_fixture):
    coordinator, _dispatcher, _tracker, signals = gap_fixture
    signals["is_shutdown"].return_value = True

    coordinator.request_repair_gap("BTCUSDT", "1m", "2024-01-01", "2024-01-02")

    signals["transition_fsm"].assert_not_called()
    coordinator._thread_manager.submit.assert_not_called()


def test_request_repair_all_gaps_transitions_and_submits(gap_fixture):
    coordinator, _dispatcher, _tracker, signals = gap_fixture
    thread_manager = coordinator._thread_manager

    coordinator.request_repair_all_gaps("BTCUSDT", "1m")

    signals["transition_fsm"].assert_called_once_with(UIMode.SYNCING)
    method, symbol, interval, token = thread_manager.submit.call_args.args
    assert method == coordinator.run_repair_all_gaps
    assert (symbol, interval) == ("BTCUSDT", "1m")
    assert token is coordinator.cancellation_token
