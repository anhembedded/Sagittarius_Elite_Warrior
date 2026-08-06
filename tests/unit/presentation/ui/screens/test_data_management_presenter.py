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
def mock_app():
    app = Mock()
    app.container = Mock()
    mock_thread_mgr = Mock()
    # Assume any resolve calls return the mock_thread_mgr for simplicity in this isolated test
    app.container.resolve.return_value = mock_thread_mgr
    app.mock_thread_mgr = mock_thread_mgr
    return app


@pytest.fixture
def mock_view():
    view = Mock()
    view.cbo_symbol.currentText.return_value = "BTCUSDT"
    view.cbo_interval.currentText.return_value = "1m"
    view.chk_custom_time.isChecked.return_value = False
    return view


def test_on_sync_data_no_custom_time(mock_view, mock_app):
    presenter = DataManagementPresenter(mock_view, mock_app)

    # Trigger sync
    presenter._on_sync_data()

    # Assert UI lock was called
    mock_view.apply_ui_mode.assert_called_with("LOCKED")

    # Assert background task was submitted to thread manager
    assert mock_app.mock_thread_mgr.submit.call_count == 1

    # Extract the spawned task (it's a local function)
    task_func = mock_app.mock_thread_mgr.submit.call_args[0][0]

    # Execute the task manually
    task_func()

    # Assert command dispatch
    assert mock_app.dispatch.call_count == 2
    dispatched_cmd = mock_app.dispatch.call_args_list[0][0][1]

    assert isinstance(dispatched_cmd, SyncMarketDataCommand)
    assert dispatched_cmd.symbols == ["BTCUSDT"]
    assert dispatched_cmd.interval.value == "1m"
    assert dispatched_cmd.start_time is None
    assert dispatched_cmd.end_time is None


def test_on_sync_data_with_custom_time(mock_view, mock_app):
    presenter = DataManagementPresenter(mock_view, mock_app)

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
    task_func = mock_app.mock_thread_mgr.submit.call_args[0][0]

    # Execute the task manually
    task_func()

    # Assert command dispatch
    assert mock_app.dispatch.call_count == 2
    dispatched_cmd = mock_app.dispatch.call_args_list[0][0][1]

    assert isinstance(dispatched_cmd, SyncMarketDataCommand)
    assert dispatched_cmd.symbols == ["BTCUSDT"]
    assert dispatched_cmd.start_time == start_dt.replace(tzinfo=timezone.utc)
    assert dispatched_cmd.end_time == end_dt.replace(tzinfo=timezone.utc)
