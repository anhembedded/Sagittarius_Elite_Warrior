import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from PySide6.QtCore import Qt

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Delay importing PySide6 and app code until within the test or fixture
# to ensure QT_QPA_PLATFORM is evaluated early.
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.main import create_app
from Binace_Bot.src.presentation.ui.main_window import MainWindow

_MOCK_KLINE_COUNT = 5


def _build_mock_klines(symbol: str, interval: str = "1m") -> list[MarketData]:
    """Newest-first MarketData list, matching what the real repository
    returns (DashboardPresenter reverses it before rendering)."""
    base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
    klines = []
    for i in range(_MOCK_KLINE_COUNT):
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
                symbol=symbol,
                interval=interval,
                open_time=open_time,
                open_price=100.0 + i,
                high_price=101.0 + i,
                low_price=99.0 + i,
                close_price=100.5 + i,
                volume=10.0,
                close_time=close_time,
                quote_asset_volume=1000.0,
                number_of_trades=5,
                taker_buy_base_asset_volume=5.0,
                taker_buy_quote_asset_volume=500.0,
            )
        )
    klines.reverse()
    return klines


@pytest.fixture
def app_engine(request, monkeypatch):
    """
    Boot the Sagittarius Engine with all configurations but mock the
    dispatcher backend. Defaults to dev.mode=False (matching app_config.json);
    parametrize indirectly with `True` to boot with dev mode on, e.g.:
    `@pytest.mark.parametrize("app_engine", [True], indirect=True)`.
    """
    dev_mode = getattr(request, "param", False)
    config_manager = ConfigManager()

    # Resolve the config path relative to this test file — 5 levels up from
    # tests/integration/presentation/ui/<this file> reaches the Binace_Bot
    # root (previously only 4, which silently resolved to tests/ instead:
    # every JsonSource.read() returned {} on a missing file, so app/user/
    # ui_matrix config — including the whole UI-matrix enable/disable
    # mechanism — was a silent no-op in every test in this file).
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    user_json = os.path.join(base_dir, "src", "config", "user_config.json")
    ui_matrix_json = os.path.join(base_dir, "src", "config", "ui_matrix.json")

    config_manager.load_json(app_json)
    config_manager.load_json(user_json)
    config_manager.load_json(ui_matrix_json)
    if dev_mode:
        config_manager.load_dict({"dev.mode": True})

    engine = create_app(config_manager)

    # Mock the internal dispatcher to intercept commands and queries
    # instead of doing real Binance/DB calls.
    def mock_dispatch(command_type, command_obj):
        # Always return success structure
        response = MagicMock()
        response.success = True
        if command_type is GetHistoricalKlinesQuery:
            # Real candles so chart-rendering features have something to
            # render, instead of the generic empty-list default below.
            response.data = _build_mock_klines(command_obj.symbol)
        else:
            response.data = []  # Empty list to avoid DB operations
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


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_board_full_feature_walkthrough(qtbot, main_window, app_engine):
    """
    Walks through every feature currently reachable on the Dev Board screen
    in one continuous sequence — this screen is used for day-to-day
    development, so a broken button here blocks manual testing entirely.
    Covers: Load History, live-tick chart updates, Start/Stop Stream, and
    Clear Logs.
    """
    qtbot.addWidget(main_window)

    # Navigate to the Dev Board
    btn_dashboard = main_window._sidebar._buttons["dashboard"]
    qtbot.mouseClick(btn_dashboard, Qt.LeftButton)

    dashboard_cfg = main_window._router._registry.get("dashboard")
    presenter = dashboard_cfg["presenter_instance"]
    view = dashboard_cfg["view_instance"]
    assert presenter.fsm.current_state.value == "IDLE"

    # --- 1. Load History -------------------------------------------------
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    chart_card = view.chart_cards[0]
    assert chart_card.symbol == "ETHUSDT"
    assert len(chart_card._raw_history) == _MOCK_KLINE_COUNT

    # --- 2. Start Stream (Auto-Sync -> reload history -> open stream) ----
    with qtbot.waitSignal(presenter.ui_stream_success_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.start_stream_button, Qt.LeftButton)
    assert presenter.fsm.current_state.value == "LIVE"
    assert view.control_card.stop_stream_button.isEnabled()

    # --- 3. Live tick -> chart update (simulates the WebSocket adapter) --
    history_before = len(chart_card._raw_history)
    closed_tick = MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=datetime(2024, 1, 1, 1, 0, tzinfo=timezone.utc),
        open_price=200.0,
        high_price=201.0,
        low_price=199.0,
        close_price=200.5,
        volume=20.0,
        close_time=datetime(2024, 1, 1, 1, 1, tzinfo=timezone.utc),
        quote_asset_volume=2000.0,
        number_of_trades=8,
        taker_buy_base_asset_volume=10.0,
        taker_buy_quote_asset_volume=1000.0,
        is_closed=True,
    )
    with qtbot.waitSignal(presenter.ui_chart_update_signal, timeout=2000):
        app_engine.event_bus.emit(MarketTickEvent(market_data=closed_tick))

    # A closed candle is appended to history, not held as the live candle.
    assert len(chart_card._raw_history) == history_before + 1
    assert chart_card._live_candle is None

    # --- 4. Clear Logs -----------------------------------------------------
    assert view.monitor_card.text_edit.toPlainText() != ""
    qtbot.mouseClick(view.monitor_card.btn_clear, Qt.LeftButton)
    # The generic click-logger (connected after clear_logs_clicked) leaves one
    # "User clicked" line behind, confirming the clear itself happened rather
    # than erasing every trace of it.
    remaining_log = view.monitor_card.text_edit.toPlainText()
    assert remaining_log.count("\n") == 0
    assert 'User clicked "Clear"' in remaining_log

    # --- 5. Stop Stream ------------------------------------------------
    qtbot.mouseClick(view.control_card.stop_stream_button, Qt.LeftButton)
    assert presenter.fsm.current_state.value == "IDLE"


def test_sanity_dev_mode_off_by_default_no_click_logging(qtbot, main_window):
    """
    dev.mode defaults to False (app_config.json) — clicking a button must NOT
    produce a "User clicked" line, proving BaseView/BasePresenter's automatic
    activation genuinely stays off for a normal (non---dev) run.
    """
    qtbot.addWidget(main_window)

    btn_dashboard = main_window._sidebar._buttons["dashboard"]
    qtbot.mouseClick(btn_dashboard, Qt.LeftButton)
    dashboard_cfg = main_window._router._registry.get("dashboard")
    view = dashboard_cfg["view_instance"]

    qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    assert "User clicked" not in view.monitor_card.text_edit.toPlainText()


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_mode_on_enables_click_logging(qtbot, main_window, app_engine):
    """
    With dev.mode=True (the real --dev flow, via app_engine's indirect
    parametrization), clicking a button on either screen must produce a
    "User clicked" line — proving activation happens through the actual
    MainWindow -> PresenterManager -> BasePresenter -> BaseView chain, not
    just the isolated BaseView mechanism (see test_base_view_click_logging.py).
    """
    qtbot.addWidget(main_window)

    btn_dashboard = main_window._sidebar._buttons["dashboard"]
    qtbot.mouseClick(btn_dashboard, Qt.LeftButton)
    dashboard_cfg = main_window._router._registry.get("dashboard")
    view = dashboard_cfg["view_instance"]

    qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    assert 'User clicked "Load History"' in view.monitor_card.text_edit.toPlainText()
    assert view.control_card.start_stream_button.isEnabled()
