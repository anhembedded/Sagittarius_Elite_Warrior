import os
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

# Delay importing PySide6 and app code until within the test or fixture
# to ensure QT_QPA_PLATFORM is evaluated early.
from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Binace_Bot.src.domain.entities.market_data import MarketData
from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent
from Binace_Bot.src.main import create_app
from Binace_Bot.src.presentation.ui.main_window import MainWindow
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

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
def app_engine(request, monkeypatch, tmp_path):
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
    # every JsonSource.read() returned {} on a missing file, so app/user
    # config was a silent no-op in every test in this file).
    base_dir = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    )
    app_json = os.path.join(base_dir, "src", "config", "app_config.json")
    real_user_json = os.path.join(base_dir, "src", "config", "user_config.json")

    # The writable source is a tmp copy of the real user_config.json, not
    # the real file: Settings' Save button now calls ConfigManager.save(),
    # and a sanity test overwriting the actual repo config on every run
    # would be both a bad side effect and non-hermetic across parallel runs.
    user_json = tmp_path / "user_config.json"
    if os.path.exists(real_user_json):
        with open(real_user_json) as src:
            user_json.write_text(src.read())
    else:
        user_json.write_text("{}")

    config_manager.load_json(app_json)
    config_manager.load_json(str(user_json), writable=True)
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


def test_sanity_boot_and_dashboard(qtbot, main_window, navigate, qml_item):
    """
    Test that the app boots correctly, navigation to Dashboard works,
    and Start Stream safely triggers FSM transition to LOCKED.
    """
    qtbot.addWidget(main_window)

    # Labeled "Dev Board" (not "Dashboard") to avoid implying this is the
    # app's end-user dashboard — it's a developer testbed screen (BOT-014).
    sidebar_root = main_window._sidebar.quick_widget.rootObject()
    assert qml_item(sidebar_root, "navButton_dashboard").property("text") == "Dev Board"

    # Navigate to dashboard
    dashboard_cfg = navigate("dashboard")
    assert dashboard_cfg is not None
    assert dashboard_cfg["view_instance"] is not None

    presenter = dashboard_cfg["presenter_instance"]
    view = dashboard_cfg["view_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # Simulate user clicking "Start Live" on the Dev Board (BOT-030 Phase 4 —
    # QML button, in the System Controls card of DevBoardPanel.qml).
    with qtbot.waitSignal(presenter.ui_stream_success_signal, timeout=2000):
        qml_item(view.quick_widget.rootObject(), "btnStart").clicked.emit()

    # After a successful mock dispatch, the state should ideally return to LIVE
    # but the sequence in _on_start_stream triggers async thread.
    # Our mocked dispatcher returns instantly, so we can verify if
    # FSM at least transitioned correctly.
    assert presenter.fsm.current_state.value in ["LOCKED", "LIVE", "ERROR"]


def test_sanity_data_management_sync(qtbot, main_window, navigate, qml_item, qapp):
    """
    Database screen (BOT-030 Phase 3 — QML). Loads through the router, and a
    real QML "Sync Current" click drives the presenter's FSM into LOCKED —
    the same behavior the QtWidgets version asserted, through the new UI.
    """
    qtbot.addWidget(main_window)

    data_mgt_cfg = navigate("data_management")
    assert data_mgt_cfg is not None
    view = data_mgt_cfg["view_instance"]
    assert view is not None
    qapp.processEvents()

    assert view.quick_widget.errors() == []
    presenter = data_mgt_cfg["presenter_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # Simulate user clicking "Sync Current"
    qml_item(view.quick_widget.rootObject(), "btnSyncData").clicked.emit()

    # waitUntil (not a bare processEvents()+assert): when this screen is
    # navigated to right after a screen that spun up a real background
    # thread (e.g. the Dev Board's Start Live in test_sanity_boot_and_dashboard,
    # which runs immediately before this test in file order), the QML
    # click's delivery can take a few extra event-loop iterations — root-
    # caused via a standalone repro script that isolated it to genuine
    # event-delivery latency (a bounded poll always converges), not a
    # dropped click or broken FSM matrix.
    qtbot.waitUntil(lambda: presenter.fsm.current_state.value == "LOCKED", timeout=2000)


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_board_full_feature_walkthrough(
    qtbot, main_window, app_engine, navigate, qml_item, qapp
):
    """
    Walks through every feature currently reachable on the Dev Board screen
    in one continuous sequence — this screen is used for day-to-day
    development, so a broken button here blocks manual testing entirely.
    Covers: Load History, live-tick chart updates, Start/Stop Stream, and
    Clear Logs — driven through DevBoardPanel.qml (BOT-030 Phase 4).
    """
    qtbot.addWidget(main_window)

    dashboard_cfg = navigate("dashboard")
    presenter = dashboard_cfg["presenter_instance"]
    view = dashboard_cfg["view_instance"]
    assert view.quick_widget.errors() == []
    root = view.quick_widget.rootObject()
    assert presenter.fsm.current_state.value == "IDLE"

    # --- 1. Load History -------------------------------------------------
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qml_item(root, "btnLoadHistory").clicked.emit()

    chart_card = view.chart_cards[0]
    assert chart_card.symbol == "ETHUSDT"
    assert len(chart_card._raw_history) == _MOCK_KLINE_COUNT

    # --- 2. Start Stream (Auto-Sync -> reload history -> open stream) ----
    with qtbot.waitSignal(presenter.ui_stream_success_signal, timeout=2000):
        qml_item(root, "btnStart").clicked.emit()
    qapp.processEvents()
    assert presenter.fsm.current_state.value == "LIVE"
    assert qml_item(root, "btnStop").property("enabled") is True

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
    assert len(view._view_model.log_model.entries) > 0
    # LogPanel.qml's Clear button calls the log model's clear() Slot
    # directly — no Presenter round-trip (same as MonitorCard's old wiring).
    qml_item(root, "btnClearLog").clicked.emit()
    assert view._view_model.log_model.entries == []

    # --- 5. Stop Stream ------------------------------------------------
    qml_item(root, "btnStop").clicked.emit()
    assert presenter.fsm.current_state.value == "IDLE"


def test_sanity_dev_mode_off_by_default_no_click_logging(
    qtbot, main_window, navigate, qml_item
):
    """
    dev.mode defaults to False (app_config.json) — clicking a button must NOT
    produce a "User clicked" line, proving BaseView/BasePresenter's automatic
    activation genuinely stays off for a normal (non---dev) run.
    """
    qtbot.addWidget(main_window)

    view = navigate("dashboard")["view_instance"]
    root = view.quick_widget.rootObject()

    qml_item(root, "btnLoadHistory").clicked.emit()

    assert not any(
        "User clicked" in entry.message for entry in view._view_model.log_model.entries
    )


def test_sanity_settings_screen_save(qtbot, main_window, navigate, qml_item, qapp):
    """
    API & Credentials screen (BOT-030 Phase 2 — QML). Proves the screen
    loads through the router, its fields populate from IConfig, and a real
    QML Save click reaches the presenter — all while the QtWidgets chart
    screens keep working alongside it.
    """
    qtbot.addWidget(main_window)

    sidebar_root = main_window._sidebar.quick_widget.rootObject()
    assert (
        qml_item(sidebar_root, "navButton_settings").property("text")
        == "API & Credentials"
    )

    settings_cfg = navigate("settings")
    assert settings_cfg is not None
    view = settings_cfg["view_instance"]
    assert view is not None
    qapp.processEvents()

    assert view.quick_widget.errors() == []
    root = view.quick_widget.rootObject()

    # Fields populated from IConfig (user_config.json) on load.
    assert qml_item(root, "txtDefaultInterval").property("text") != ""

    qml_item(root, "btnSaveCredentials").clicked.emit()
    qapp.processEvents()
    assert qml_item(root, "lblStatus").property("text") != ""

    # Navigating away and back to the other screens must still work —
    # coexistence, not a one-way trip.
    assert navigate("dashboard")["view_instance"] is not None
    assert navigate("data_management")["view_instance"] is not None


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_mode_click_logging_does_not_reach_qml_buttons(
    qtbot, main_window, app_engine, navigate, qml_item
):
    """
    Documents a known, pre-existing limitation rather than silently losing
    coverage of it: dev.mode=True's auto click-logging
    (_ButtonClickWatcher in sagittarius_engine's base_view.py) instruments
    QPushButton instances found via QWidget.findChildren() — it cannot see
    a QQuickWidget's internal QML scene graph. This has been true for every
    QML screen since BOT-030 Phase 2 (Settings), but was only ever pinned
    for the Dev Board back when its buttons were still QtWidgets
    (ControlCard). Phase 4 moved those to QML too, so this test now
    documents the same (unchanged) limitation here — see
    test_base_view_click_logging.py for the isolated mechanism this exercises
    end-to-end.
    """
    qtbot.addWidget(main_window)

    view = navigate("dashboard")["view_instance"]
    root = view.quick_widget.rootObject()

    qml_item(root, "btnLoadHistory").clicked.emit()

    assert not any(
        "User clicked" in entry.message for entry in view._view_model.log_model.entries
    )
