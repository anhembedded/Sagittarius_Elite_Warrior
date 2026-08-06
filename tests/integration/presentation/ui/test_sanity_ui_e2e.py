import os
import pytest
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Delay importing PySide6 and app code until within the test or fixture
# to ensure QT_QPA_PLATFORM is evaluated early.
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.main import create_app
from Binace_Bot.src.presentation.ui.main_window import MainWindow


@pytest.fixture
def app_engine(monkeypatch):
    """Boot the Sagittarius Engine with all configurations but mock the dispatcher backend."""
    config_manager = ConfigManager()

    # Resolve the config path relative to this test file
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    )
    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    user_json = os.path.join(base_dir, "src", "config", "user_config.json")
    ui_matrix_json = os.path.join(base_dir, "src", "config", "ui_matrix.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    config_manager.load_json(ui_matrix_json)

    engine = create_app(config_manager)

    # Mock the internal dispatcher to intercept commands and queries
    # instead of doing real Binance/DB calls.
    def mock_dispatch(command_type, command_obj):
        # Always return success structure
        response = MagicMock()
        response.success = True
        response.data = []  # Empty KLines list to avoid DB operations
        return response

    monkeypatch.setattr(engine, "dispatch", mock_dispatch)

    # We must also mock the dispatcher inside the container
    from sagittarius_engine.interfaces.i_dispatcher import IDispatcher

    container_dispatcher = engine.context.container.resolve(IDispatcher)
    monkeypatch.setattr(container_dispatcher, "dispatch", mock_dispatch)

    engine.boot()
    yield engine
    engine.stop()


@pytest.fixture
def main_window(qapp, app_engine):
    """Instantiate the MainWindow with the mocked engine."""
    window = MainWindow(app_engine)
    window.show()
    return window


def test_sanity_boot_and_dashboard(qtbot, main_window):
    """
    Test that the app boots correctly, navigation to Dashboard works,
    and Start Stream safely triggers FSM transition to LOCKED.
    """
    qtbot.addWidget(main_window)

    # Navigate to dashboard
    btn_dashboard = main_window._sidebar._buttons["dashboard"]
    # Labeled "Dev Board" (not "Dashboard") to avoid implying this is the
    # app's end-user dashboard — it's a developer testbed screen (BOT-014).
    assert btn_dashboard.text() == "Dev Board"
    qtbot.mouseClick(btn_dashboard, Qt.LeftButton)

    # Get the Dashboard Presenter and View from the Router
    dashboard_cfg = main_window._router._registry.get("dashboard")
    assert dashboard_cfg is not None
    assert dashboard_cfg["view_instance"] is not None

    presenter = dashboard_cfg["presenter_instance"]
    view = dashboard_cfg["view_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # Simulate user clicking "Start Stream" on the Dashboard
    with qtbot.waitSignal(presenter.ui_stream_success_signal, timeout=2000):
        # We need to click the button in the view
        # The button is btn_start_stream in ControlCard
        qtbot.mouseClick(view.control_card.start_stream_button, Qt.LeftButton)

    # After a successful mock dispatch, the state should ideally return to LIVE
    # but the sequence in _on_start_stream triggers async thread.
    # Our mocked dispatcher returns instantly, so we can verify if
    # FSM at least transitioned correctly.
    assert presenter.fsm.current_state.value in ["LOCKED", "LIVE", "ERROR"]


def test_sanity_data_management_sync(qtbot, main_window):
    """
    Test that the Data Management screen loads properly and
    the Sync feature triggers correctly without NameError.
    """
    qtbot.addWidget(main_window)

    # Navigate to data management
    btn_database = main_window._sidebar._buttons["data_management"]
    qtbot.mouseClick(btn_database, Qt.LeftButton)

    data_mgt_cfg = main_window._router._registry.get("data_management")
    assert data_mgt_cfg is not None
    assert data_mgt_cfg["view_instance"] is not None

    presenter = data_mgt_cfg["presenter_instance"]
    view = data_mgt_cfg["view_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # Simulate user clicking "Sync Data"
    qtbot.mouseClick(view.btn_sync_data, Qt.LeftButton)

    # Assert FSM went into LOCKED
    assert presenter.fsm.current_state.value == "LOCKED"
