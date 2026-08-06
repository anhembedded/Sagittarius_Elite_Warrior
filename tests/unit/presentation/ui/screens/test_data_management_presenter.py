import pytest
from unittest.mock import Mock
from datetime import datetime, timezone
from Binace_Bot.src.presentation.ui.screens.data_management.data_management_presenter import (
    DataManagementPresenter,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)


@pytest.fixture
def mock_container():
    container = Mock()
    mock_thread_mgr = Mock()
    mock_dispatcher = Mock()

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
    container.mock_thread_mgr = mock_thread_mgr
    container.mock_dispatcher = mock_dispatcher
    return container


@pytest.fixture
def mock_view():
    view = Mock()
    view.cbo_symbol.currentText.return_value = "BTCUSDT"
    view.cbo_interval.currentText.return_value = "1m"
    view.chk_custom_time.isChecked.return_value = False
    return view


def test_on_sync_data_no_custom_time(mock_view, mock_container):
    presenter = DataManagementPresenter(mock_view, mock_container)

    # Trigger sync
    presenter._on_sync_data()

    # Assert UI lock was called via FSM
    assert presenter.fsm.current_state.name == "LOCKED"

    # Assert background task was submitted to thread manager
    assert mock_container.mock_thread_mgr.submit.call_count == 1

    # Extract the spawned task (it's a local function)
    task_func = mock_container.mock_thread_mgr.submit.call_args[0][0]

    # Execute the task manually
    task_func()

    # Assert command dispatch
    assert mock_container.mock_dispatcher.dispatch.call_count == 2
    dispatched_cmd = mock_container.mock_dispatcher.dispatch.call_args_list[0][0][1]

    assert isinstance(dispatched_cmd, SyncMarketDataCommand)
    assert dispatched_cmd.symbols == ["BTCUSDT"]
    assert dispatched_cmd.interval.value == "1m"
    assert dispatched_cmd.start_time is None
    assert dispatched_cmd.end_time is None


def test_on_sync_data_with_custom_time(mock_view, mock_container):
    presenter = DataManagementPresenter(mock_view, mock_container)

    # Enable custom time
    mock_view.chk_custom_time.isChecked.return_value = True

    dt_from_mock = Mock()
    dt_to_mock = Mock()

    start_dt = datetime(2023, 1, 1)
    end_dt = datetime(2023, 1, 2)

    dt_from_mock.toPython.return_value = start_dt
    dt_to_mock.toPython.return_value = end_dt

    mock_view.dt_from.dateTime.return_value = dt_from_mock
    mock_view.dt_to.dateTime.return_value = dt_to_mock

    # Trigger sync
    presenter._on_sync_data()

    # Extract the spawned task
    task_func = mock_container.mock_thread_mgr.submit.call_args[0][0]

    # Execute the task manually
    task_func()

    # Assert command dispatch
    assert mock_container.mock_dispatcher.dispatch.call_count == 2
    dispatched_cmd = mock_container.mock_dispatcher.dispatch.call_args_list[0][0][1]

    assert isinstance(dispatched_cmd, SyncMarketDataCommand)
    assert dispatched_cmd.symbols == ["BTCUSDT"]
    assert dispatched_cmd.start_time == start_dt.replace(tzinfo=timezone.utc)
    assert dispatched_cmd.end_time == end_dt.replace(tzinfo=timezone.utc)
