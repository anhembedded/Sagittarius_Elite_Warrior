import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication

from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import (
    DashboardView,
)
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.application.use_cases.stream.start_live_stream.command import (
    StartLiveStreamCommand,
)


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


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
    mock_config.get.return_value = matrix

    # Mock IThreadManager - execute immediately instead of thread
    from sagittarius_engine.interfaces.i_thread_manager import IThreadManager

    mock_thread_mgr = MagicMock()

    def submit_sync(task):
        task()  # Execute synchronously in the test

    mock_thread_mgr.submit.side_effect = submit_sync

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        if interface == IThreadManager:
            return mock_thread_mgr
        return MagicMock()

    app.container.resolve.side_effect = resolve_side_effect
    return app


def test_dashboard_integration_start_stream_chart_rendering(qapp, mock_app):
    """
    Simulates clicking Start Stream, and verifies that the history data is properly
    rendered and repainted on the ChartCard.
    """
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app)
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
            response = MagicMock()
            response.data = [mock_kline]
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
        "Binace_Bot.src.presentation.ui.components.chart_card.FastCandlestickItem.update"
    ) as mock_update:
        # Trigger Start Stream
        view.control_card.sig_start_clicked.emit()

        # Check if the chart was created
        assert len(presenter.active_charts) == 2
        card = presenter.active_charts["BTCUSDT"]

        # Assert history was added to the candlestick
        assert len(card.candlestick.history_data) == 1

        # Assert update() was called to trigger a repaint
        assert mock_update.called, (
            "FastCandlestickItem.update() was not called! The chart will not draw."
        )
