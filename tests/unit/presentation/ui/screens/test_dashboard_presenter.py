import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import (
    DashboardPresenter,
)
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
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

    # Mock IConfig
    from sagittarius_engine.interfaces.i_config import IConfig

    mock_config = MagicMock()
    matrix = {
        "IDLE": {"start_stream_button": True, "stop_stream_button": False},
        "LIVE": {"start_stream_button": False, "stop_stream_button": True},
        "LOCKED": {"start_stream_button": False, "stop_stream_button": False},
        "ERROR": {"start_stream_button": True, "stop_stream_button": False},
    }
    mock_config.get.return_value = matrix

    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        return MagicMock()

    app.container.resolve.side_effect = resolve_side_effect
    return app


@pytest.fixture
def mock_view():
    view = MagicMock()
    # Mock render_symbol_cards
    view.render_symbol_cards.return_value = []

    # Needs a real mock for signals to be connectable, but PySide signals are tricky to mock perfectly.
    # We will use MagicMock for them. The presenter calls .connect() on them.
    return view


def test_dashboard_presenter_initialization(qapp, mock_view, mock_app):
    presenter = DashboardPresenter(mock_view, mock_app)
    assert presenter.view == mock_view
    assert presenter.app == mock_app


def test_dashboard_presenter_load_history_dispatches_query(qapp, mock_view, mock_app):
    presenter = DashboardPresenter(mock_view, mock_app)

    # Mocking ensure_chart_cards to return a mock card
    mock_card = MagicMock()
    mock_card.symbol = "BTCUSDT"
    presenter._ensure_chart_cards = MagicMock(return_value=[mock_card])

    # Call the slot
    presenter._on_load_history()

    # Assert dispatch was called with GetHistoricalKlinesQuery
    mock_app.dispatch.assert_called()
    call_args = mock_app.dispatch.call_args[0]
    assert call_args[0] == GetHistoricalKlinesQuery
    assert call_args[1].symbol == "BTCUSDT"


def test_dashboard_presenter_load_history_handles_exception(qapp, mock_view, mock_app):
    presenter = DashboardPresenter(mock_view, mock_app)

    # Force _ensure_chart_cards to raise an exception
    presenter._ensure_chart_cards = MagicMock(side_effect=ValueError("Test Exception"))

    # Track logs
    logs = []
    presenter.ui_log_signal.connect(lambda msg: logs.append(msg))

    # Should NOT raise because @safe_ui_action catches it
    presenter._on_load_history()

    # Verify the error was logged
    assert any("Test Exception" in log for log in logs)
    assert any("_on_load_history failed" in log for log in logs)
