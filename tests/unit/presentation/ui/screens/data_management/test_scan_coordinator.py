from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases import (
    DatabaseStatusDTO,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.common.action_ownership_tracker import (
    ActionOutcome,
    ActionOwnershipTracker,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.coordinators import (
    DataManagementActionKind,
    ScanCoordinator,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_signal_payloads import (
    StatusRowUpdate,
)


@pytest.fixture
def scan_fixture():
    view_model = Mock()
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "15m"
    view_model.symbols = ["BTCUSDT"]
    view_model.intervals = ["15m"]

    dispatcher = Mock()
    thread_manager = Mock()
    tracker = ActionOwnershipTracker[DataManagementActionKind, object, UIMode]()
    market_data_repo = Mock()

    signals = {
        "ui_log": Mock(),
        "ui_error_log": Mock(),
        "ui_status_table": Mock(),
        "ui_remove_symbol": Mock(),
        "ui_clear_table": Mock(),
        "ui_stats_refresh": Mock(),
        "ui_unlock": Mock(),
        "ui_symbol_options": Mock(),
        "transition_fsm": Mock(return_value=True),
        "get_fsm_state": Mock(return_value=UIMode.IDLE),
    }

    coordinator = ScanCoordinator(
        view_model=view_model,
        dispatcher=dispatcher,
        thread_manager=thread_manager,
        tracker=tracker,
        market_data_repo=market_data_repo,
        ui_log_signal=signals["ui_log"],
        ui_error_log_signal=signals["ui_error_log"],
        ui_status_table_signal=signals["ui_status_table"],
        ui_remove_symbol_signal=signals["ui_remove_symbol"],
        ui_clear_table_signal=signals["ui_clear_table"],
        ui_stats_refresh_signal=signals["ui_stats_refresh"],
        ui_unlock_signal=signals["ui_unlock"],
        ui_symbol_options_signal=signals["ui_symbol_options"],
        transition_fsm=signals["transition_fsm"],
        get_current_fsm_state=signals["get_fsm_state"],
    )

    return coordinator, dispatcher, market_data_repo, tracker, signals


def test_scan_coordinator_auto_discover_populates_table(scan_fixture):
    coordinator, dispatcher, _, tracker, signals = scan_fixture

    status_dto = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="15m",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="100",
        gaps="0",
        status_text="OK",
    )
    dispatcher.dispatch.side_effect = [
        ["BTCUSDT", "ETHUSDT"],  # ListAvailableSymbolsQuery
        [status_dto],  # ScanAllDatabasesQuery
    ]

    coordinator.run_auto_discover()

    signals["ui_symbol_options"].assert_called_once_with(["BTCUSDT", "ETHUSDT"])
    # EPIC-008G §3: signal mang `StatusRowUpdate` thay vì 6 chuỗi vị trí, nên
    # assert theo TÊN trường — hoán nhầm 2 cột giờ làm test đỏ chứ không lọt.
    signals["ui_status_table"].assert_called_once_with(
        StatusRowUpdate(
            symbol="BTCUSDT",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="100",
            status_text="OK",
            interval="15m",
        )
    )
    signals["ui_stats_refresh"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_check_status_success(scan_fixture):
    coordinator, dispatcher, _, tracker, signals = scan_fixture

    status_dto = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="15m",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="500",
        gaps="0",
        status_text="OK",
    )
    dispatcher.dispatch.return_value = status_dto

    coordinator.run_check_status("BTCUSDT", "15m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], GetDatabaseStatusQuery)
    # EPIC-008G §3: signal mang `StatusRowUpdate` thay vì 6 chuỗi vị trí, nên
    # assert theo TÊN trường — hoán nhầm 2 cột giờ làm test đỏ chứ không lọt.
    signals["ui_status_table"].assert_called_once_with(
        StatusRowUpdate(
            symbol="BTCUSDT",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="500",
            status_text="OK",
            interval="15m",
        )
    )
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_clear_data_success(scan_fixture):
    coordinator, dispatcher, _, tracker, signals = scan_fixture

    dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=100, success=True, message="Data cleared"
    )

    coordinator.run_clear_data("BTCUSDT", "15m")

    dispatcher.dispatch.assert_called_once()
    assert isinstance(dispatcher.dispatch.call_args[0][1], ClearMarketDataCommand)
    signals["ui_remove_symbol"].assert_called_once_with("BTCUSDT", "15m")
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_purge_all_success(scan_fixture):
    coordinator, dispatcher, _, tracker, signals = scan_fixture

    dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=500, success=True, message="Purged all"
    )

    coordinator.run_purge_all()

    signals["ui_clear_table"].assert_called_once()
    signals["ui_unlock"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_vacuum_uses_injected_repository(scan_fixture):
    coordinator, _, market_data_repo, tracker, signals = scan_fixture

    coordinator.run_vacuum()

    market_data_repo.vacuum.assert_called_once()
    signals["ui_stats_refresh"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_cancel_is_wired_into_scan_query(scan_fixture):
    """BUG-041: coordinator cancellation must reach the application handler."""
    coordinator, dispatcher, _, _, _ = scan_fixture
    dispatcher.dispatch.return_value = []

    cancellation_token = coordinator.create_cancellation_token()
    coordinator.cancel()
    coordinator.run_scan_all(["BTCUSDT"], ["1m"], cancellation_token)

    query = dispatcher.dispatch.call_args.args[1]
    assert query.cancellation_requested is not None
    assert query.cancellation_requested() is True
