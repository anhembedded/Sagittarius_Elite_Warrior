"""
Tests for the Database screen's presenter (BOT-030 / BOT-112A — Storage Vault).

Design notes carried over and enforced here:
- IThreadManager is resolved once in __init__ (not per-method).
- Background work is submitted as `self._run_x(args...)` via
  thread_manager.submit(method, *args) — NOT as inline closures.
- _on_check_all_status dispatches ScanAllDatabasesQuery (single dispatch).
- Multi-timeframe selection, shard auto-discovery, clearing, and purging.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.database.clear_market_data import (
    ClearMarketDataResult,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.domain.value_objects.timeframe import TimeFrame
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


# ---------------------------------------------------------------------------
# Single sync (Multi-timeframe)
# ---------------------------------------------------------------------------


def test_on_sync_data_submits_background_task(presenter, view_model, mock_thread_mgr):
    """Must lock the FSM and submit _run_single_sync with selected symbol & interval."""
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "15m"

    view_model.requestSync()

    assert presenter.fsm.current_state == UIMode.SYNCING
    mock_thread_mgr.submit.assert_called_with(
        presenter._run_single_sync, "BTCUSDT", "15m", None, None
    )


def test_run_single_sync_dispatches_command(presenter, mock_dispatcher):
    presenter.fsm.transition_to(UIMode.SYNCING)

    presenter._run_single_sync("ETHUSDT", "1h", None, None)

    command_type, command = next(
        call.args
        for call in mock_dispatcher.dispatch.call_args_list
        if call.args[0] is SyncMarketDataCommand
    )
    assert command_type is SyncMarketDataCommand
    assert command.symbols == ["ETHUSDT"]
    assert command.interval == TimeFrame.ONE_HOUR


def test_custom_time_range_is_parsed_and_passed_through(
    presenter, view_model, mock_thread_mgr
):
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1h"
    view_model.useCustomTime = True
    view_model.fromDateTime = "2024-01-01 00:00"
    view_model.toDateTime = "2024-01-02 12:30"

    view_model.requestSync()

    _, symbol, interval, start, end = mock_thread_mgr.submit.call_args.args
    assert symbol == "BTCUSDT"
    assert interval == "1h"
    assert start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 2, 12, 30, tzinfo=UTC)


def test_invalid_custom_time_range_is_rejected_without_syncing(
    presenter, view_model, mock_thread_mgr
):
    view_model.useCustomTime = True
    view_model.fromDateTime = "not-a-date"
    view_model.toDateTime = "2024-01-02 12:30"

    view_model.requestSync()

    # Must not submit single sync when invalid
    for call in mock_thread_mgr.submit.call_args_list:
        assert call.args[0] != presenter._run_single_sync
    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.log_model.entries[-1].level == "error"


# ---------------------------------------------------------------------------
# Scanning & Auto-Discovery
# ---------------------------------------------------------------------------


def test_on_check_all_status_submits_background_task(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestCheckAllStatus()

    assert presenter.fsm.current_state == UIMode.SCANNING
    method, symbols, intervals = mock_thread_mgr.submit.call_args.args
    assert method == presenter._run_scan_all
    assert symbols == list(view_model.symbols)
    assert intervals == list(view_model.intervals)


def test_run_scan_all_dispatches_single_query(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = []
    presenter.fsm.transition_to(UIMode.SCANNING)

    presenter._run_scan_all(["BTCUSDT"], ["1m", "5m"])

    assert any(
        call.args[0] is ScanAllDatabasesQuery
        for call in mock_dispatcher.dispatch.call_args_list
    )


def test_run_scan_all_fills_the_table_model(presenter, view_model, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = [
        DatabaseStatusDTO(
            symbol="BTCUSDT",
            interval="1m",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="1440",
            gaps="0",
            status_text="OK",
        ),
        DatabaseStatusDTO(
            symbol="ETHUSDT",
            interval="15m",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="1200",
            gaps="3",
            status_text="3 gaps found!",
        ),
    ]
    presenter.fsm.transition_to(UIMode.SCANNING)

    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m", "15m"])

    assert view_model.status_model.rowCount() == 2
    assert view_model.status_model.gap_targets() == [("ETHUSDT", "15m")]


def test_on_check_status_submits_background_task(
    presenter, view_model, mock_thread_mgr
):
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "1h"

    view_model.requestCheckStatus()

    mock_thread_mgr.submit.assert_called_with(
        presenter._run_check_status, "BTCUSDT", "1h"
    )
    assert presenter.fsm.current_state == UIMode.SCANNING


def test_run_check_status_populates_the_row_for_the_selection(
    presenter, view_model, mock_dispatcher
):
    response = Mock()
    response.data = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="1h",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="24",
        gaps="0",
        status_text="OK",
    )
    mock_dispatcher.dispatch.return_value = response

    presenter.fsm.transition_to(UIMode.SCANNING)
    presenter._run_check_status("BTCUSDT", "1h")

    rows = view_model.status_model.rows
    assert len(rows) == 1
    assert rows[0].symbol == "BTCUSDT"
    assert rows[0].interval == "1h"
    assert rows[0].status_text == "OK"
    assert presenter.fsm.current_state == UIMode.IDLE


# ---------------------------------------------------------------------------
# Bulk gap sync
# ---------------------------------------------------------------------------


def test_sync_all_gaps_uses_only_unhealthy_rows(presenter, view_model, mock_thread_mgr):
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "10", "OK", "1m")
    view_model.status_model.upsert_row("ETHUSDT", "a", "b", "5", "2 gaps found!", "15m")

    view_model.requestSyncAllGaps()

    method, targets = mock_thread_mgr.submit.call_args.args
    assert method == presenter._run_bulk_sync
    assert targets == [("ETHUSDT", "15m")]
    assert view_model.progressMaximum == 1
    assert view_model.progressVisible is True


def test_sync_all_gaps_with_no_gaps_does_nothing(
    presenter, view_model, mock_thread_mgr
):
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "10", "OK", "1m")

    view_model.requestSyncAllGaps()

    # Must not submit bulk sync
    for call in mock_thread_mgr.submit.call_args_list:
        assert call.args[0] != presenter._run_bulk_sync
    assert presenter.fsm.current_state == UIMode.IDLE


# ---------------------------------------------------------------------------
# Clear & Purge Actions
# ---------------------------------------------------------------------------


def test_on_clear_data_submits_clear_worker(presenter, view_model, mock_thread_mgr):
    view_model.selectedSymbol = "BTCUSDT"
    view_model.selectedInterval = "5m"

    view_model.requestClearData()

    assert presenter.fsm.current_state == UIMode.CLEARING
    mock_thread_mgr.submit.assert_called_with(
        presenter._run_clear_data, "BTCUSDT", "5m"
    )


def test_run_clear_data_dispatches_command_and_updates_model(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=500,
        success=True,
        message="Đã xóa thành công 500 nến của BTCUSDT (5m).",
    )
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "500", "OK", "5m")
    assert view_model.status_model.rowCount() == 1

    presenter.fsm.transition_to(UIMode.CLEARING)
    presenter._run_clear_data("BTCUSDT", "5m")

    assert view_model.status_model.rowCount() == 0
    assert view_model.log_model.entries[-1].level == "info"
    assert presenter.fsm.current_state == UIMode.IDLE


def test_on_purge_all_submits_purge_worker(presenter, view_model, mock_thread_mgr):
    view_model.requestPurgeAll()

    assert presenter.fsm.current_state == UIMode.CLEARING
    mock_thread_mgr.submit.assert_called_with(presenter._run_purge_all)


def test_run_purge_all_dispatches_command_and_clears_all(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = ClearMarketDataResult(
        deleted_records=5,
        success=True,
        message="Đã xóa toàn bộ cơ sở dữ liệu (5 database shards).",
    )
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "100", "OK", "1m")
    view_model.status_model.upsert_row("ETHUSDT", "a", "b", "200", "OK", "1h")

    presenter.fsm.transition_to(UIMode.CLEARING)
    presenter._run_purge_all()

    assert view_model.status_model.rowCount() == 0
    assert presenter.fsm.current_state == UIMode.IDLE


def test_on_vacuum_submits_vacuum_worker(presenter, view_model, mock_thread_mgr):
    view_model.requestVacuum()
    mock_thread_mgr.submit.assert_called_with(presenter._run_vacuum)


# ---------------------------------------------------------------------------
# Stat tiles
# ---------------------------------------------------------------------------


def test_stored_records_tile_sums_scanned_totals(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = [
        DatabaseStatusDTO("BTCUSDT", "1m", "a", "b", "1440", "0", "OK"),
        DatabaseStatusDTO("ETHUSDT", "15m", "a", "b", "1,200", "0", "OK"),
    ]
    presenter.fsm.transition_to(UIMode.SCANNING)
    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m", "15m"])

    presenter._refresh_stats()

    assert view_model.storedRecords == "2,640"


def test_dead_screen_does_not_break_app_wide_logging(qapp, mock_container, request):
    import logging

    view = DataManagementView()
    presenter = DataManagementPresenter(view, mock_container)
    handler = presenter._log_handler
    assert handler in logging.getLogger("App").handlers

    del presenter
    view.deleteLater()
    view.destroyed.emit()
    qapp.processEvents()

    logging.getLogger("App.IconLoader").warning("icon missing")
    assert handler not in logging.getLogger("App").handlers


# ---------------------------------------------------------------------------
# BUG-018 — startup auto-discovery must not fire an IDLE -> IDLE transition
# ---------------------------------------------------------------------------


def _dispatch_by_query_type(scan_results):
    """Auto-discovery dispatches two different queries; a single
    `return_value` would hand the DTO list to the symbol-options path too."""

    def _dispatch(query_type, _query):
        if query_type is ScanAllDatabasesQuery:
            return scan_results
        return ["BTCUSDT", "ETHUSDT"]

    return _dispatch


def test_startup_auto_discovery_refreshes_the_stat_tiles(
    presenter, view_model, mock_dispatcher
):
    """Regression (BUG-018): auto-discovery runs from __init__ while the FSM
    is still IDLE, but its `finally` block used to emit the *unlock* signal —
    `_unlock_ui` then called `transition_to(IDLE)` from IDLE, which the
    transition matrix rejects. The raised `InvalidStateTransitionError` aborted
    the slot before `_refresh_stats()`, so "Stored KLines Records" stayed "—"
    forever even though the table below it had just been filled with rows."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type(
        [
            DatabaseStatusDTO("BTCUSDT", "1m", "a", "b", "1440", "0", "OK"),
            DatabaseStatusDTO("ETHUSDT", "15m", "a", "b", "1,200", "0", "OK"),
        ]
    )
    assert presenter.fsm.current_state == UIMode.IDLE

    presenter._run_auto_discover()

    assert view_model.status_model.rowCount() == 2
    assert view_model.storedRecords == "2,640"
    assert presenter.fsm.current_state == UIMode.IDLE


def test_startup_auto_discovery_does_not_unlock_a_sync_started_meanwhile(
    presenter, view_model, mock_dispatcher
):
    """The screen stays interactive during auto-discovery (a Binance symbol
    fetch can take seconds), so the user can start a sync before it finishes.
    Auto-discovery never locked the UI, so it must never unlock it — otherwise
    every control re-enables mid-sync."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type([])
    presenter.fsm.transition_to(UIMode.SYNCING)

    presenter._run_auto_discover()

    assert presenter.fsm.current_state == UIMode.SYNCING


def test_vacuum_refreshes_the_stat_tiles(presenter, view_model, mock_dispatcher):
    """Same defect class as BUG-018: `_on_vacuum` submits its worker without
    locking the FSM, so the worker's `finally` unlock also transitioned
    IDLE -> IDLE. VACUUM reclaims disk space, so the size tile is exactly what
    must refresh afterwards."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type(
        [DatabaseStatusDTO("BTCUSDT", "1m", "a", "b", "500", "0", "OK")]
    )
    presenter.fsm.transition_to(UIMode.SCANNING)
    presenter._run_scan_all(["BTCUSDT"], ["1m"])

    presenter._run_vacuum()

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.storedRecords == "500"


def test_unlock_ui_from_a_locked_state_returns_to_idle(presenter):
    presenter.fsm.transition_to(UIMode.SCANNING)

    presenter._unlock_ui()

    assert presenter.fsm.current_state == UIMode.IDLE


def test_unlock_ui_is_idempotent_when_already_idle(
    presenter, view_model, mock_dispatcher
):
    """Restoring the UI to IDLE is a request for an end state, not for a
    transition — being there already is success, not an error to raise on."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type(
        [DatabaseStatusDTO("BTCUSDT", "1m", "a", "b", "777", "0", "OK")]
    )
    presenter.fsm.transition_to(UIMode.SCANNING)
    presenter._run_scan_all(["BTCUSDT"], ["1m"])
    assert presenter.fsm.current_state == UIMode.IDLE

    presenter._unlock_ui()

    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.storedRecords == "777"


def test_data_management_view_model_supports_one_second_and_all_standard_intervals(
    view_model,
):
    """BOT-112E: Ensure 1s sub-minute timeframe and all TimeFrame VOs are exposed in intervals."""
    assert "1s" in view_model.intervals
    assert "1m" in view_model.intervals
    assert "5m" in view_model.intervals
    assert "15m" in view_model.intervals
    assert "1h" in view_model.intervals
    assert "1d" in view_model.intervals
    assert "1w" in view_model.intervals
    assert "1M" in view_model.intervals


def test_auto_discover_empty_database_logs_informative_message(
    presenter, view_model, mock_dispatcher
):
    """When disk has no databases, auto-discover should log a clear message for the user."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type([])

    presenter._run_auto_discover()

    log_entries = [
        view_model.log_model.data(view_model.log_model.index(i, 0), 257)
        for i in range(view_model.log_model.rowCount())
    ]
    assert any("Storage Vault trống" in entry for entry in log_entries)


def test_scan_all_empty_database_logs_informative_message(
    presenter, view_model, mock_dispatcher
):
    """When a scan finds 0 tables, full scan should log that no database tables were found."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type([])

    presenter._run_scan_all(["BTCUSDT"], ["1m"])

    log_entries = [
        view_model.log_model.data(view_model.log_model.index(i, 0), 257)
        for i in range(view_model.log_model.rowCount())
    ]
    assert any(
        "No database tables found in Storage Vault" in entry for entry in log_entries
    )


def test_auto_discover_empty_database_emits_storage_vault_logger(
    presenter, mock_dispatcher, caplog
):
    """Asserts that App.DataManagement emits structured [storage-vault] INFO logs."""
    mock_dispatcher.dispatch.side_effect = _dispatch_by_query_type([])
    with caplog.at_level(logging.INFO, logger="App.DataManagement"):
        presenter._run_auto_discover()

    assert any(
        "[storage-vault]" in record.message
        and "Storage Vault is empty" in record.message
        for record in caplog.records
    )
