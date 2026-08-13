"""
Tests for the Database screen's presenter (BOT-030 Phase 3 — QML).

Design notes carried over from the QtWidgets version and still enforced here:
- IThreadManager is resolved once in __init__ (not per-method).
- Background work is submitted as `self._run_x(args...)` via
  thread_manager.submit(method, *args) — NOT as inline closures.
- _on_check_all_status dispatches ScanAllDatabasesQuery (single dispatch).

Uses the REAL DataManagementViewModel and its item models (pure state, no
I/O), mocking only the genuine external dependencies.
"""

import os
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.constants import UIMode
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.data_management.data_management_view import (
    DataManagementView,
)


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
            # BOT-066: dev.mode on for the whole suite, so any exception a
            # @safe_ui_action-decorated slot swallows re-raises instead of
            # passing a test that should have failed.
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
# Single sync
# ---------------------------------------------------------------------------


def test_on_sync_data_submits_background_task(presenter, view_model, mock_thread_mgr):
    """Must lock the FSM and submit _run_single_sync to the thread manager,
    never dispatch on the main thread."""
    view_model.selectedSymbol = "BTCUSDT"

    view_model.requestSync()

    assert presenter.fsm.current_state == UIMode.SYNCING
    mock_thread_mgr.submit.assert_called_once_with(
        presenter._run_single_sync, "BTCUSDT", "1m", None, None
    )


def test_run_single_sync_dispatches_command(presenter, mock_dispatcher):
    # Real callers only reach this after _on_sync_data()/_on_sync_all_gaps()
    # has already moved the FSM to SYNCING (BOT-066: dev-mode re-raise
    # surfaced that _on_sync_complete()'s SYNCING->IDLE is invalid from
    # this fixture's default IDLE). With that fixed, _on_sync_complete()
    # now runs to completion and its own _on_check_status() dispatches a
    # second, later GetDatabaseStatusQuery call — so this must search the
    # full call list for the sync command instead of assuming it's last.
    presenter.fsm.transition_to(UIMode.SYNCING)

    presenter._run_single_sync("ETHUSDT", "1h", None, None)

    command_type, command = next(
        call.args
        for call in mock_dispatcher.dispatch.call_args_list
        if call.args[0] is SyncMarketDataCommand
    )
    assert command_type is SyncMarketDataCommand
    assert command.symbols == ["ETHUSDT"]


def test_custom_time_range_is_parsed_and_passed_through(
    presenter, view_model, mock_thread_mgr
):
    view_model.selectedSymbol = "BTCUSDT"
    view_model.useCustomTime = True
    view_model.fromDateTime = "2024-01-01 00:00"
    view_model.toDateTime = "2024-01-02 12:30"

    view_model.requestSync()

    _, _, _, start, end = mock_thread_mgr.submit.call_args.args
    assert start == datetime(2024, 1, 1, 0, 0, tzinfo=UTC)
    assert end == datetime(2024, 1, 2, 12, 30, tzinfo=UTC)


def test_invalid_custom_time_range_is_rejected_without_syncing(
    presenter, view_model, mock_thread_mgr
):
    """Opting into a custom range then typing garbage must NOT silently fall
    back to the default window — that would quietly fetch the wrong data."""
    view_model.useCustomTime = True
    view_model.fromDateTime = "not-a-date"
    view_model.toDateTime = "2024-01-02 12:30"

    view_model.requestSync()

    mock_thread_mgr.submit.assert_not_called()
    assert presenter.fsm.current_state == UIMode.IDLE
    assert view_model.log_model.entries[-1].level == "error"


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def test_on_check_all_status_submits_background_task(
    presenter, view_model, mock_thread_mgr
):
    view_model.requestCheckAllStatus()

    assert presenter.fsm.current_state == UIMode.SCANNING
    method, symbols, intervals = mock_thread_mgr.submit.call_args.args
    assert method == presenter._run_scan_all
    assert symbols == list(view_model.symbols)
    assert intervals == ["1m"]


def test_run_scan_all_dispatches_single_query(presenter, mock_dispatcher):
    mock_dispatcher.dispatch.return_value = []
    # Real callers only reach this after _on_check_all_status() has already
    # moved the FSM to SCANNING (BOT-066: see test_run_single_sync_dispatches_command).
    presenter.fsm.transition_to(UIMode.SCANNING)

    presenter._run_scan_all(["BTCUSDT"], ["1m"])

    assert mock_dispatcher.dispatch.call_count == 1
    assert mock_dispatcher.dispatch.call_args.args[0] is ScanAllDatabasesQuery


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
            interval="1m",
            first_record="2024-01-01",
            last_record="2024-01-02",
            total_candles="1200",
            gaps="3",
            status_text="3 gaps found!",
        ),
    ]
    presenter.fsm.transition_to(UIMode.SCANNING)

    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m"])

    assert view_model.status_model.rowCount() == 2
    assert view_model.status_model.gap_targets() == ["ETHUSDT"]


def test_on_check_status_populates_the_row_for_the_selection(
    presenter, view_model, mock_dispatcher
):
    response = Mock()
    response.data = DatabaseStatusDTO(
        symbol="BTCUSDT",
        interval="1m",
        first_record="2024-01-01",
        last_record="2024-01-02",
        total_candles="1440",
        gaps="0",
        status_text="OK",
    )
    mock_dispatcher.dispatch.return_value = response
    view_model.selectedSymbol = "BTCUSDT"

    view_model.requestCheckStatus()

    rows = view_model.status_model.rows
    assert len(rows) == 1
    assert rows[0].symbol == "BTCUSDT"
    assert rows[0].status_text == "OK"


# ---------------------------------------------------------------------------
# Bulk gap sync
# ---------------------------------------------------------------------------


def test_sync_all_gaps_uses_only_unhealthy_rows(presenter, view_model, mock_thread_mgr):
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "10", "OK")
    view_model.status_model.upsert_row("ETHUSDT", "a", "b", "5", "2 gaps found!")

    view_model.requestSyncAllGaps()

    method, targets = mock_thread_mgr.submit.call_args.args
    assert method == presenter._run_bulk_sync
    assert targets == ["ETHUSDT"]
    assert view_model.progressMaximum == 1
    assert view_model.progressVisible is True


def test_sync_all_gaps_with_no_gaps_does_nothing(
    presenter, view_model, mock_thread_mgr
):
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "10", "OK")

    view_model.requestSyncAllGaps()

    mock_thread_mgr.submit.assert_not_called()
    assert presenter.fsm.current_state == UIMode.IDLE


# ---------------------------------------------------------------------------
# Stat tiles
# ---------------------------------------------------------------------------


def test_stored_records_tile_sums_scanned_totals(
    presenter, view_model, mock_dispatcher
):
    mock_dispatcher.dispatch.return_value = [
        DatabaseStatusDTO("BTCUSDT", "1m", "a", "b", "1440", "0", "OK"),
        DatabaseStatusDTO("ETHUSDT", "1m", "a", "b", "1,200", "0", "OK"),
    ]
    presenter.fsm.transition_to(UIMode.SCANNING)
    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m"])

    presenter._refresh_stats()

    assert view_model.storedRecords == "2,640"


def test_non_numeric_totals_do_not_break_the_stat_tile(presenter, view_model):
    """total_candles is a display string from the DTO — an "N/A" must be
    skipped rather than crash the tile."""
    view_model.status_model.upsert_row("BTCUSDT", "a", "b", "N/A", "OK")
    view_model.status_model.upsert_row("ETHUSDT", "a", "b", "100", "OK")

    presenter._refresh_stats()

    assert view_model.storedRecords == "100"


def test_dead_screen_does_not_break_app_wide_logging(qapp, mock_container, request):
    """
    Regression test: SignalLogHandler is attached to the app-wide "App"
    logger, so it outlives the screen that installed it. Once that screen's
    C++ object is deleted the bound signal raises, and because every `App.*`
    logger propagates there, ONE dead screen used to break logging for the
    whole app (first seen as unrelated IconLoader tests failing).
    """
    import logging

    view = DataManagementView()
    presenter = DataManagementPresenter(view, mock_container)
    handler = presenter._log_handler
    assert handler in logging.getLogger("App").handlers

    del presenter
    view.deleteLater()
    view.destroyed.emit()  # what Qt fires when the C++ object goes away
    qapp.processEvents()

    # Logging through any App.* child must still work, not raise.
    logging.getLogger("App.IconLoader").warning("icon missing")
    assert handler not in logging.getLogger("App").handlers


def test_database_size_is_unknown_when_config_has_no_usable_path(presenter, view_model):
    """A stat tile must never be able to take the screen down, whatever the
    config holds."""
    presenter.config.get.return_value = None
    assert presenter._database_size_text() == "—"

    presenter.config.get.return_value = Mock()  # not a path at all
    assert presenter._database_size_text() == "—"


def test_on_clear_data_transitions_state_and_logs(presenter, view_model):
    view_model.selectedSymbol = "BTCUSDT"
    view_model.requestClearData()

    assert presenter.fsm.current_state == UIMode.CLEARING
    assert view_model.log_model.entries[-1].level == "info"
