from concurrent.futures import Future
from unittest.mock import MagicMock

import pytest
from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Sagittarius_Elite_Warrior.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)


@pytest.fixture
def mock_app():
    app = MagicMock()
    app.event_bus = MagicMock()
    app.container = MagicMock()

    from sagittarius_engine.interfaces.i_config import IConfig

    mock_config = MagicMock()
    matrix = {
        "IDLE": {"start_stream_button": True, "stop_stream_button": False},
        "LIVE": {"start_stream_button": False, "stop_stream_button": True},
        "LOCKED": {"start_stream_button": False, "stop_stream_button": False},
        "ERROR": {"start_stream_button": True, "stop_stream_button": False},
    }
    mock_config.get_all.return_value = matrix
    # Key-aware, not a blanket stub: BasePresenter reads the UI matrix via
    # get_all() (above), but also reads individual keys via get() (e.g.
    # dev.mode, BOT-034's CHART_CARD_MIN_FETCH_CANDLES) — those must fall
    # through to the caller's own `default`, not receive the matrix dict.
    mock_config.get.side_effect = lambda key, default=None, cast=None: default

    # Mock IThreadManager - execute immediately instead of thread
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_thread_mgr = MagicMock()

    def submit_sync(task, *args, **kwargs):
        # Must return a real Future, not None: ExclusiveAction.submit()
        # (BOT-069, landed after this fixture was first written) calls
        # `future.add_done_callback(...)` on whatever IThreadManager.submit()
        # returns, to release its exclusive-action slot once the task
        # settles. Returning None here used to work because nothing read
        # the return value — now it crashes with AttributeError, which
        # @safe_ui_action (BOT-066, also later) catches and logs instead of
        # raising, so the crash was invisible and just left the
        # "load_history" slot stuck forever, silently rejecting every
        # subsequent _on_start_stream() call via its own try_start() guard.
        future: Future = Future()
        try:
            future.set_result(task(*args, **kwargs))  # Execute synchronously
        except Exception as exc:  # noqa: BLE001 - mirror the real thread pool's contract
            future.set_exception(exc)
        return future

    mock_thread_mgr.submit.side_effect = submit_sync

    def resolve_side_effect(interface):
        from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

        if interface == IConfig:
            return mock_config
        if interface == IThreadManager:
            return mock_thread_mgr
        if interface == IDispatcher:
            return app
        return MagicMock()

    app.container.resolve.side_effect = resolve_side_effect
    return app


def test_dashboard_integration_start_stream_chart_rendering(qapp, mock_app):
    """
    Simulates clicking Start Stream, and verifies that the history data is properly
    rendered and repainted on the ChartCard.
    """
    mock_app.resolve.return_value = mock_app
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app.container)
    view.presenter = presenter

    # Mock the return values for the dispatch calls
    def mock_dispatch(cmd_type, cmd):
        if cmd_type == GetHistoricalKlinesQuery:
            # Return fake klines
            mock_kline = MagicMock()
            mock_kline.close_time.timestamp.return_value = 1600000000.0
            mock_kline.open_price = 1000.0
            mock_kline.high_price = 1100.0
            mock_kline.low_price = 900.0
            mock_kline.close_price = 1050.0
            mock_kline.volume = 250.0
            response = MagicMock()
            # Keyed by symbol, not a flat list: GetHistoricalKlinesQuery now
            # takes `symbol` as a list (multi-symbol support,
            # handler.py::_execute_multi), which returns dict[str,
            # list[MarketData]] — one entry per requested symbol. A flat
            # list here fails stream_lifecycle_controller.py's own
            # `isinstance(results, dict)` guard, which logs "Unexpected
            # response format" and returns before ever touching the
            # candlestick — never a raised exception, so this stayed
            # invisible until BUG-047 traced it.
            response.data = {sym: [mock_kline] for sym in cmd.symbol}
            return response
        if cmd_type == StartLiveStreamCommand:
            response = MagicMock()
            response.success = True
            return response
        return MagicMock()

    mock_app.dispatch.side_effect = mock_dispatch

    # Track update() calls on the candlestick item
    from unittest.mock import patch

    with patch(
        "Sagittarius_Elite_Warrior.src.presentation.ui.components.chart_card.FastCandlestickItem.update"
    ):
        # Trigger Load History first
        presenter._on_load_history()

        # Trigger Start Stream
        presenter._on_start_stream()

        # Check if the chart was created
        assert len(presenter.active_charts) == 1
        # Keyed by whatever symbol the screen loaded — EPIC-010H made that come
        # from Settings rather than a module constant.
        card = presenter.active_charts[presenter._active_symbol]

        # Assert history was added to the candlestick
        assert len(card.candlestick.history_data) == 1
