"""
Tests for DashboardPresenter.

Key design changes from the refactor:
- IThreadManager resolved once in __init__.
- _on_load_history no longer calls dispatcher directly on the main thread.
  It submits _run_load_history(symbols, interval_str, limit) to the thread manager.
- _on_start_stream submits _run_sync_and_start to the thread manager.
- No inline closures anywhere.
"""

import pytest
from unittest.mock import MagicMock

from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Binace_Bot.src.application.use_cases.sync.sync_market_data.command import (
    SyncMarketDataCommand,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_thread_mgr():
    return MagicMock()


@pytest.fixture
def mock_dispatcher():
    return MagicMock()


@pytest.fixture
def mock_container(mock_thread_mgr, mock_dispatcher):
    container = MagicMock()

    from sagittarius_engine.interfaces.i_config import IConfig
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_config = MagicMock()
    matrix = {
        "IDLE": {"start_stream_button": True, "stop_stream_button": False},
        "LIVE": {"start_stream_button": False, "stop_stream_button": True},
        "LOCKED": {"start_stream_button": False, "stop_stream_button": False},
        "ERROR": {"start_stream_button": True, "stop_stream_button": False},
    }
    mock_config.get_all.return_value = {"main": matrix}

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IDispatcher:
            return mock_dispatcher
        if interface == IThreadManager:
            return mock_thread_mgr
        return MagicMock()

    container.resolve.side_effect = resolve_side_effect
    return container


@pytest.fixture
def mock_view():
    view = MagicMock()
    view.render_symbol_cards.return_value = []
    return view


@pytest.fixture
def presenter(qapp, mock_view, mock_container):
    return DashboardPresenter(mock_view, mock_container)


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_initialization(presenter, mock_view, mock_container):
    assert presenter.view == mock_view
    assert presenter.container == mock_container
    assert presenter.fsm.current_state.name == "IDLE"


# ---------------------------------------------------------------------------
# _on_load_history — must NOT block the main thread
# ---------------------------------------------------------------------------


def test_on_load_history_submits_background_task(presenter, mock_thread_mgr):
    """_on_load_history submits _run_load_history to thread manager — no direct dispatch."""
    presenter._on_load_history()

    assert mock_thread_mgr.submit.call_count == 1
    submit_args = mock_thread_mgr.submit.call_args[0]

    # First arg must be the dedicated background method, not a closure
    assert submit_args[0] == presenter._run_load_history


def test_on_load_history_does_not_dispatch_on_main_thread(presenter, mock_dispatcher):
    """_on_load_history must NOT call dispatcher directly — that belongs in the background."""
    presenter._on_load_history()
    mock_dispatcher.dispatch.assert_not_called()


def test_run_load_history_dispatches_query_per_symbol(presenter, mock_dispatcher):
    """_run_load_history (background) dispatches one GetHistoricalKlinesQuery per symbol."""
    mock_kline = MagicMock()
    mock_kline.close_time.timestamp.return_value = 1700000000.0
    mock_kline.open_price = 40000
    mock_kline.high_price = 41000
    mock_kline.low_price = 39000
    mock_kline.close_price = 40500
    mock_kline.volume = 12.5

    mock_dispatcher.dispatch.return_value = [mock_kline]

    symbols = ["BTCUSDT", "ETHUSDT"]
    presenter._run_load_history(symbols, "1m", 5000)

    assert mock_dispatcher.dispatch.call_count == 2
    for i, call_args in enumerate(mock_dispatcher.dispatch.call_args_list):
        dispatched_type, dispatched_query = call_args[0]
        assert dispatched_type == GetHistoricalKlinesQuery
        assert dispatched_query.symbol == symbols[i]
        assert dispatched_query.interval == "1m"
        assert dispatched_query.limit == 5000
        assert dispatched_query.order_by_desc is True


def test_run_load_history_handles_exception_per_symbol(presenter, mock_dispatcher):
    """An exception for one symbol must not abort the rest of the load."""
    mock_dispatcher.dispatch.side_effect = [
        Exception("DB error"),
        [MagicMock()],
    ]

    logs = []
    presenter.ui_log_signal.connect(logs.append)

    # Should not raise
    presenter._run_load_history(["BTCUSDT", "ETHUSDT"], "1m", 100)

    assert any("BTCUSDT" in log for log in logs)


# ---------------------------------------------------------------------------
# _on_start_stream — submits full sync+stream workflow to background
# ---------------------------------------------------------------------------


def test_on_start_stream_locks_ui_and_submits_task(presenter, mock_thread_mgr):
    """_on_start_stream must lock FSM and submit _run_sync_and_start."""
    presenter._on_start_stream()

    assert presenter.fsm.current_state.name == "LOCKED"
    assert mock_thread_mgr.submit.call_count == 1

    submit_args = mock_thread_mgr.submit.call_args[0]
    assert submit_args[0] == presenter._run_sync_and_start


def test_run_sync_and_start_full_workflow(presenter, mock_dispatcher):
    """_run_sync_and_start dispatches Sync → HistoricalKlines → StartLiveStream in order."""
    mock_dispatcher.dispatch.return_value = []

    from Binace_Bot.src.domain.value_objects.timeframe import TimeFrame

    presenter._run_sync_and_start(["BTCUSDT"], TimeFrame("1m"), "1m", 5000)

    call_types = [args[0][0] for args in mock_dispatcher.dispatch.call_args_list]
    assert SyncMarketDataCommand in call_types
    assert GetHistoricalKlinesQuery in call_types
    assert StartLiveStreamCommand in call_types

    # Order matters: Sync first, then Query, then Stream
    sync_idx = call_types.index(SyncMarketDataCommand)
    query_idx = call_types.index(GetHistoricalKlinesQuery)
    stream_idx = call_types.index(StartLiveStreamCommand)
    assert sync_idx < query_idx < stream_idx


# ---------------------------------------------------------------------------
# Exception safety
# ---------------------------------------------------------------------------


def test_on_load_history_exception_is_caught_by_safe_ui_action(presenter, mock_view):
    """@safe_ui_action catches exceptions from _ensure_chart_cards without crashing."""
    presenter._ensure_chart_cards = MagicMock(side_effect=ValueError("Test Exception"))

    logs = []
    presenter.ui_log_signal.connect(logs.append)

    presenter._on_load_history()

    assert any(
        "Test Exception" in log or "_on_load_history failed" in log for log in logs
    )
