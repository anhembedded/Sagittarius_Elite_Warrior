"""
Tests for DataManagementPresenter.

Key design changes from the refactor:
- IThreadManager is resolved once in __init__ (not per-method).
- Background work is submitted as self._run_single_sync(symbol, interval, start, end)
  via thread_manager.submit(method, *args) — NOT as inline closures.
- _on_check_all_status dispatches ScanAllDatabasesQuery (single dispatch, no loop).
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timezone

from Binace_Bot.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)
from Binace_Bot.src.application.use_cases.queries.scan_all_databases.query import (
    DatabaseStatusDTO,
    ScanAllDatabasesQuery,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


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
        from sagittarius_engine.interfaces.i_thread_manager import IThreadManager
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
        from sagittarius_engine.interfaces.i_config import IConfig

        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IConfig:
            mock_config = Mock()
            matrix = {"IDLE": {"btn_sync": True}, "LOCKED": {"btn_sync": False}}
            mock_config.get_all.return_value = {"data_management": matrix}
            return mock_config
        return Mock()

    container.resolve.side_effect = resolve_mock
    return container


@pytest.fixture
def mock_view():
    view = Mock()
    view.cbo_symbol.currentText.return_value = "BTCUSDT"
    view.cbo_interval.currentText.return_value = "1m"
    view.cbo_symbol.count.return_value = 2
    view.cbo_symbol.itemText.side_effect = lambda i: ["BTCUSDT", "ETHUSDT"][i]
    view.cbo_interval.count.return_value = 1
    view.cbo_interval.itemText.side_effect = lambda i: ["1m"][i]
    view.chk_custom_time.isChecked.return_value = False
    return view


@pytest.fixture
def presenter(mock_view, mock_container):
    return DataManagementPresenter(mock_view, mock_container)


# ---------------------------------------------------------------------------
# _on_sync_data — no custom time
# ---------------------------------------------------------------------------


def test_on_sync_data_submits_background_task(presenter, mock_thread_mgr):
    """_on_sync_data must lock FSM and submit _run_single_sync to thread manager."""
    presenter._on_sync_data()

    assert presenter.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1

    # Submitted as (method, symbol, interval, start_time, end_time)
    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_single_sync
    assert submit_args[1] == "BTCUSDT"  # symbol
    assert submit_args[2] == "1m"  # interval
    assert submit_args[3] is None  # start_time
    assert submit_args[4] is None  # end_time


def test_run_single_sync_dispatches_command(presenter, mock_dispatcher):
    """_run_single_sync (background method) dispatches SyncMarketDataCommand."""
    presenter._run_single_sync("BTCUSDT", "1m", None, None)

    assert mock_dispatcher.dispatch.call_count >= 1
    dispatched_type, dispatched_cmd = mock_dispatcher.dispatch.call_args_list[0][0]

    assert dispatched_type == SyncMarketDataCommand
    assert isinstance(dispatched_cmd, SyncMarketDataCommand)
    assert dispatched_cmd.symbols == ["BTCUSDT"]
    assert dispatched_cmd.interval.value == "1m"
    assert dispatched_cmd.start_time is None
    assert dispatched_cmd.end_time is None


# ---------------------------------------------------------------------------
# _on_sync_data — with custom time
# ---------------------------------------------------------------------------


def test_on_sync_data_with_custom_time_passes_timestamps(
    presenter, mock_thread_mgr, mock_view
):
    """When chk_custom_time is checked, start/end times are captured on the main thread."""
    mock_view.chk_custom_time.isChecked.return_value = True

    start_dt = datetime(2023, 1, 1)
    end_dt = datetime(2023, 1, 2)

    dt_from_mock = Mock()
    dt_from_mock.toPython.return_value = start_dt
    dt_to_mock = Mock()
    dt_to_mock.toPython.return_value = end_dt

    mock_view.dt_from.dateTime.return_value = dt_from_mock
    mock_view.dt_to.dateTime.return_value = dt_to_mock

    presenter._on_sync_data()

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[3] == start_dt.replace(tzinfo=timezone.utc)
    assert submit_args[4] == end_dt.replace(tzinfo=timezone.utc)


def test_run_single_sync_with_timestamps_dispatches_correctly(
    presenter, mock_dispatcher
):
    """_run_single_sync correctly passes start/end times into the command."""
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = datetime(2023, 1, 2, tzinfo=timezone.utc)

    presenter._run_single_sync("BTCUSDT", "1m", start, end)

    _, dispatched_cmd = mock_dispatcher.dispatch.call_args_list[0][0]
    assert dispatched_cmd.start_time == start
    assert dispatched_cmd.end_time == end


# ---------------------------------------------------------------------------
# _on_check_all_status — dispatches ScanAllDatabasesQuery (single dispatch)
# ---------------------------------------------------------------------------


def test_on_check_all_status_submits_background_task(presenter, mock_thread_mgr):
    """_on_check_all_status must lock FSM and submit _run_scan_all."""
    presenter._on_check_all_status()

    assert presenter.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_scan_all


def test_run_scan_all_dispatches_single_query(presenter, mock_dispatcher):
    """_run_scan_all dispatches exactly ONE ScanAllDatabasesQuery — no per-pair loop."""
    mock_dispatcher.dispatch.return_value = []  # Empty result list

    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m"])

    assert mock_dispatcher.dispatch.call_count == 1
    dispatched_type, dispatched_query = mock_dispatcher.dispatch.call_args[0]

    assert dispatched_type == ScanAllDatabasesQuery
    assert isinstance(dispatched_query, ScanAllDatabasesQuery)
    assert dispatched_query.symbols == ["BTCUSDT", "ETHUSDT"]
    assert dispatched_query.intervals == ["1m"]


def test_run_scan_all_emits_signal_per_dto(presenter, mock_dispatcher):
    """Each DatabaseStatusDTO in the result emits one ui_status_table_signal."""
    dtos = [
        DatabaseStatusDTO(
            symbol="BTCUSDT",
            interval="1m",
            first_record="2024-01-01",
            last_record="2024-06-01",
            total_candles="500",
            gaps="0",
            status_text="OK",
        ),
        DatabaseStatusDTO(
            symbol="ETHUSDT",
            interval="1m",
            first_record="2024-01-01",
            last_record="2024-06-01",
            total_candles="300",
            gaps="2",
            status_text="2 gaps found!",
        ),
    ]
    mock_dispatcher.dispatch.return_value = dtos

    emitted = []
    presenter.ui_status_table_signal.connect(
        lambda sym, intv, fr, lr, tot, stat: emitted.append(sym)
    )

    presenter._run_scan_all(["BTCUSDT", "ETHUSDT"], ["1m"])

    assert emitted == ["BTCUSDT", "ETHUSDT"]
