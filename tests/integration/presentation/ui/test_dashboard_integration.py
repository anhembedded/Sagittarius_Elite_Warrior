import pytest
from unittest.mock import MagicMock
from PySide6.QtWidgets import QApplication
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_view import DashboardView
from Binace_Bot.src.presentation.ui.screens.dashboard.dashboard_presenter import DashboardPresenter
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import GetHistoricalKlinesQuery

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
        "ERROR": {"start_stream_button": True, "stop_stream_button": False}
    }
    mock_config.get.return_value = matrix
    
    def resolve_side_effect(interface):
        if interface == IConfig:
            return mock_config
        return MagicMock()
        
    app.container.resolve.side_effect = resolve_side_effect
    return app

def test_dashboard_integration_load_history(qapp, mock_app):
    # 1. Setup View and Presenter
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app)
    view.presenter = presenter
    
    # 2. Simulate User clicking "Load History" on the ControlCard
    # Instead of clicking the button (which might require event loop processing), 
    # we emit the signal directly which the button would have emitted.
    view.control_card.sig_load_clicked.emit()
    
    # 3. Assert the Presenter caught it and interacted with the Engine
    # Note: Because the mock_app dispatch is called in the presenter, 
    # and _ensure_chart_cards will render them, we should see a dispatch.
    mock_app.dispatch.assert_called()
    call_args = mock_app.dispatch.call_args[0]
    assert call_args[0] == GetHistoricalKlinesQuery

def test_dashboard_integration_exception_fallback(qapp, mock_app):
    view = DashboardView()
    presenter = DashboardPresenter(view, mock_app)
    view.presenter = presenter
    
    # Force an exception inside the slot logic
    mock_app.dispatch.side_effect = Exception("Engine died")
    
    # Track logs
    logs = []
    presenter.ui_log_signal.connect(lambda msg: logs.append(msg))
    
    # Before click: stream buttons are default
    assert view.control_card.btn_start_stream.isEnabled()
    assert not view.control_card.btn_stop_stream.isEnabled()
    
    # Emit load history, which will hit the exception in mock_app.dispatch
    view.control_card.sig_load_clicked.emit()
    
    # The @safe_ui_action should catch it and log it
    assert any("Engine died" in log for log in logs)
    
    # The UI should have triggered the fallback recovery (set_stream_active(False))
    # which ensures the UI is unlocked.
    assert view.control_card.btn_start_stream.isEnabled()
    assert not view.control_card.btn_stop_stream.isEnabled()
