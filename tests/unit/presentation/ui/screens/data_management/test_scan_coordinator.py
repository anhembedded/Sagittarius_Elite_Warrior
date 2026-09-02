from __future__ import annotations

from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataCommand,
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.database.prune_empty_shards import (
    PruneEmptyShardsCommand,
    PruneEmptyShardsResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_database_status.query import (
    GetDatabaseStatusQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.list_available_symbols import (
    ListAvailableSymbolsQuery,
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


def test_scan_coordinator_auto_discover_never_opens_a_shard_session(scan_fixture):
    """BOT-120 — screen-open auto-discover must stay a directory listing: only
    ListAvailableSymbolsQuery (cached, cheap) plus a call to
    `list_available_shards()`. It must never dispatch ScanAllDatabasesQuery or
    PruneEmptyShardsCommand — those open one SQLite session per shard and are
    now explicit-action-only (see run_scan_all)."""
    coordinator, dispatcher, market_data_repo, tracker, signals = scan_fixture

    dispatcher.dispatch.return_value = [
        "BTCUSDT",
        "ETHUSDT",
    ]  # ListAvailableSymbolsQuery
    market_data_repo.list_available_shards.return_value = ["BTCUSDT"]

    coordinator.run_auto_discover()

    dispatcher.dispatch.assert_called_once()
    assert dispatcher.dispatch.call_args.args[0] is ListAvailableSymbolsQuery
    market_data_repo.list_available_shards.assert_called_once()
    signals["ui_symbol_options"].assert_called_once_with(["BTCUSDT", "ETHUSDT"])
    signals["ui_status_table"].assert_not_called()
    assert any(
        "1 tệp dữ liệu cục bộ" in str(call.args[0])
        for call in signals["ui_log"].call_args_list
    )
    signals["ui_stats_refresh"].assert_called_once()
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_auto_discover_reports_an_empty_vault_truthfully(
    scan_fixture,
):
    coordinator, dispatcher, market_data_repo, tracker, signals = scan_fixture

    dispatcher.dispatch.return_value = []  # ListAvailableSymbolsQuery
    market_data_repo.list_available_shards.return_value = []

    coordinator.run_auto_discover()

    signals["ui_symbol_options"].assert_not_called()
    assert any(
        "trống" in str(call.args[0]) for call in signals["ui_log"].call_args_list
    )
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_populates_table(scan_fixture):
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
        [status_dto],  # ScanAllDatabasesQuery
        PruneEmptyShardsResult(removed_symbols=[], scanned_count=0),  # BUG-078
    ]

    coordinator.run_scan_all(["BTCUSDT"], ["15m"])

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
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_dispatches_prune_and_reports_removals(
    scan_fixture,
):
    """BUG-078 / BOT-120 — the explicit full scan must dispatch
    PruneEmptyShardsCommand as its last step and surface a log line when it
    actually removed something. This used to be auto-discover's job; it moved
    here so opening every shard's session is always an explicit user action."""
    coordinator, dispatcher, _, tracker, signals = scan_fixture

    dispatcher.dispatch.side_effect = [
        [],  # ScanAllDatabasesQuery
        PruneEmptyShardsResult(
            removed_symbols=["PHANTOM1", "PHANTOM2"], scanned_count=5
        ),
    ]

    coordinator.run_scan_all([], ["1m"])

    assert dispatcher.dispatch.call_count == 2
    prune_call = dispatcher.dispatch.call_args_list[1]
    assert prune_call.args[0] is PruneEmptyShardsCommand
    assert any(
        "2 shard" in str(call.args[0]) for call in signals["ui_log"].call_args_list
    )
    assert tracker.active_outcome == ActionOutcome.SUCCEEDED


def test_scan_coordinator_scan_all_survives_prune_failure(scan_fixture):
    """A broken prune pass must not fail the whole scan-all action — it's a
    hygiene pass, not the reason the user clicked Scan All."""
    coordinator, dispatcher, _, tracker, _signals = scan_fixture

    dispatcher.dispatch.side_effect = [
        [],  # ScanAllDatabasesQuery
        Exception("disk unavailable"),  # PruneEmptyShardsCommand
    ]

    coordinator.run_scan_all([], ["1m"])

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
