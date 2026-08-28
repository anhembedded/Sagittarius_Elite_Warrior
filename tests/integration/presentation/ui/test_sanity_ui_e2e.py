import os
from datetime import UTC, datetime

import pytest

# Force offscreen rendering for headless CI environments
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
    MarketTickEvent,
)

# app_engine/main_window come from conftest.py — this file used to define
# its own near-duplicate copies (predating BOT-034), which meant the
# auto-start fallback-window override and the teardown fixes (cancellation,
# thread-pool drain, chart-card cleanup — see conftest.py's main_window
# docstring for why each exists) silently didn't apply to any test here.
# That gap didn't crash outright in this file, but nothing here was actually
# protected from the same race either — deleting the local duplicates
# instead of re-patching them a second place keeps there being exactly one
# fixture to keep correct. The one thing worth keeping from the old local
# fixture — writing to a tmp_path copy of user_config.json instead of the
# real repo file, so test_sanity_settings_screen_save's Save button doesn't
# overwrite real config — was ported into conftest.py's shared app_engine
# fixture instead of duplicated back here.
#
# Must match conftest.MOCK_KLINE_COUNT (not imported: this directory's test
# modules have no __init__.py, so they're collected as top-level modules,
# not a package — a relative `from .conftest import` would fail).
_MOCK_KLINE_COUNT = 5


def test_sanity_boot_and_dashboard(qtbot, main_window, navigate):
    """
    Test that the app boots correctly, navigation to Dashboard works, and
    BOT-034's auto-start safely drives the FSM through LOCKED to a settled
    state with no user click needed.
    """
    qtbot.addWidget(main_window)

    # Labeled "Dev Board" (not "Dashboard") to avoid implying this is the
    # app's end-user dashboard — it's a developer testbed screen (BOT-014).
    nav_button = main_window._sidebar._nav_buttons["dashboard"]
    assert nav_button.display_text == "Dev Board"

    # Navigate to dashboard
    dashboard_cfg = navigate("dashboard")
    assert dashboard_cfg is not None
    assert dashboard_cfg["view_instance"] is not None

    presenter = dashboard_cfg["presenter_instance"]

    # BOT-034: opening the Dev Board auto-starts Start Live — navigate()
    # already waited for it to settle (success or failure), so by the time
    # we get here the FSM has already gone IDLE -> LOCKED -> LIVE (or ERROR
    # on a failed mock dispatch), with no click involved. A manual "Start
    # Live" click on top of that is now a deliberate no-op (see
    # DashboardPresenter._on_start_stream's FSM-not-IDLE guard).
    assert presenter.fsm.current_state.value in ["LOCKED", "LIVE", "ERROR"]


def test_sanity_data_management_sync(qtbot, main_window, navigate, qapp):
    """
    Database screen (QtWidgets, EPIC-005E). Loads through the router, and a
    real "Sync Current" click drives the presenter's FSM into LOCKED.
    """
    qtbot.addWidget(main_window)

    data_mgt_cfg = navigate("data_management")
    assert data_mgt_cfg is not None
    view = data_mgt_cfg["view_instance"]
    assert view is not None
    qapp.processEvents()

    presenter = data_mgt_cfg["presenter_instance"]

    # Ensure starting mode is IDLE
    assert presenter.fsm.current_state.value == "IDLE"

    # Simulate user clicking "Sync Current"
    view._action_buttons["btnSyncData"].click()

    qtbot.waitUntil(
        lambda: presenter.fsm.current_state.value == "SYNCING", timeout=2000
    )


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_board_full_feature_walkthrough(
    qtbot, main_window, app_engine, navigate, qapp
):
    """
    Walks through every feature currently reachable on the Dev Board screen
    in one continuous sequence — this screen is used for day-to-day
    development, so a broken button here blocks manual testing entirely.
    Covers: Load History, live-tick chart updates, Start/Stop Stream, and
    Clear Logs — driven through `DevBoardPanel` (QtWidgets, EPIC-006D).

    BOT-034: opening the Dev Board now auto-starts Start Live, and
    navigate() already waited for it to settle — so by the time this test's
    body runs, FSM is already LIVE (not IDLE) with no click involved. A
    manual "Start Stream" click at this point is a deliberate no-op (see
    DashboardPresenter._on_start_stream's FSM-not-IDLE guard, added
    specifically because auto-start made this reachable for the first
    time) — Step 2 below asserts the auto-started state directly instead of
    re-clicking a button that would otherwise just log "ignoring".
    """
    qtbot.addWidget(main_window)

    dashboard_cfg = navigate("dashboard")
    presenter = dashboard_cfg["presenter_instance"]
    view = dashboard_cfg["view_instance"]
    panel = view._panel
    assert presenter.fsm.current_state.value == "LIVE"

    # --- 1. Load History (manual re-load, on top of auto-start's own) ----
    # Not panel._btn_load_history.click(): legitimately disabled while
    # uiMode == "LIVE" (see test_dev_board_*.py's own note on this) — same
    # target the button's own handler calls.
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        view._view_model.requestLoadHistory()

    chart_card = view.chart_cards[0]
    # EPIC-010H: the Dev Board now honours Settings' DEFAULT_SYMBOLS, so the
    # symbol it opens on depends on config rather than a module constant.
    # Asserted against the symbol actually loaded, because what this
    # walkthrough is really checking is that history arrived for the chart the
    # screen built — not which pair that happens to be.
    assert chart_card.symbol == presenter._active_symbol
    assert len(chart_card._raw_history) == _MOCK_KLINE_COUNT

    # --- 2. Start Stream — already running via auto-start ----------------
    assert presenter.fsm.current_state.value == "LIVE"
    assert panel._btn_stop.isEnabled() is True

    # --- 3. Live tick -> chart update (simulates the WebSocket adapter) --
    history_before = len(chart_card._raw_history)
    closed_tick = MarketData(
        symbol=chart_card.symbol,
        interval="1m",
        open_time=datetime(2024, 1, 1, 1, 0, tzinfo=UTC),
        open_price=200.0,
        high_price=201.0,
        low_price=199.0,
        close_price=200.5,
        volume=20.0,
        close_time=datetime(2024, 1, 1, 1, 1, tzinfo=UTC),
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
    panel._log_panel.findChild(object, "btnClearLog").click()
    assert view._view_model.log_model.entries == []

    # --- 5. Stop Stream ------------------------------------------------
    panel._btn_stop.click()
    assert presenter.fsm.current_state.value == "IDLE"


def test_sanity_dev_mode_off_by_default_no_click_logging(qtbot, main_window, navigate):
    """
    dev.mode defaults to False (app_config.json) — clicking a button must NOT
    produce a "User clicked" line, proving BaseView/BasePresenter's automatic
    activation genuinely stays off for a normal (non---dev) run.
    """
    qtbot.addWidget(main_window)

    view = navigate("dashboard")["view_instance"]
    view._view_model.requestLoadHistory()

    assert not any(
        "User clicked" in entry.message for entry in view._view_model.log_model.entries
    )


def test_sanity_settings_screen_save(qtbot, main_window, navigate, qapp):
    """
    API & Credentials screen (QtWidgets, EPIC-005D). Proves the screen loads
    through the router, its fields populate from IConfig, and a real Save
    click reaches the presenter — all while the other screens keep working
    alongside it.
    """
    qtbot.addWidget(main_window)

    nav_button = main_window._sidebar._nav_buttons["settings"]
    assert nav_button.display_text == "API & Credentials"

    settings_cfg = navigate("settings")
    assert settings_cfg is not None
    view = settings_cfg["view_instance"]
    assert view is not None
    qapp.processEvents()

    from PySide6.QtWidgets import QLabel, QPushButton

    # Fields populated from IConfig (user_config.json) on load. EPIC-014 made
    # Default Interval a picker button rather than a free-text field — its
    # only legal values are the sixteen the domain declares, and a typo in it
    # used to be ignored silently.
    assert view.findChild(QPushButton, "btnDefaultInterval").text() != ""

    view.findChild(QPushButton, "btnSaveCredentials").click()
    qapp.processEvents()
    assert view.findChild(QLabel, "lblStatus").text() != ""

    # Navigating away and back to the other screens must still work —
    # coexistence, not a one-way trip.
    assert navigate("dashboard")["view_instance"] is not None
    assert navigate("data_management")["view_instance"] is not None


@pytest.mark.parametrize("app_engine", [True], indirect=True)
def test_sanity_dev_mode_click_logging_does_not_yet_reach_the_dev_board_panel(
    qtbot, main_window, app_engine, navigate
):
    """
    Documents a still-open gap, now for a different reason than before:
    dev.mode=True's auto click-logging (`_ButtonClickWatcher` in
    sagittarius_engine's base_view.py) used to miss every Dev Board button
    because they lived inside a `QQuickWidget`'s QML scene graph
    (invisible to `QWidget.findChildren()`). EPIC-006D moved
    `DevBoardPanel` to plain QtWidgets, so that specific reason is gone —
    but clicking a real, enabled `DevBoardPanel` button (`_btn_stop`, the
    one guaranteed enabled at this point: uiMode == "LIVE" post
    auto-start) still produces no "User clicked" log line, verified
    empirically. `BasePresenter.__init__` calls
    `view.enable_dev_click_logging()` before `DashboardPresenter` ever
    calls `view.set_view_model()` (which is what actually constructs
    `DevBoardPanel` and attaches it to the splitter) — `_ButtonClickWatcher`
    is documented to pick up children added later via a `ChildAdded` event
    filter, but empirically doesn't for this specific
    lazily-built-then-`QSplitter.addWidget()`-attached case. Root cause not
    chased further here (an engine-side mechanism, not something this
    session's own changes touch) — kept as a live tripwire pointing at the
    right two lines to start from if this needs fixing."""
    qtbot.addWidget(main_window)

    view = navigate("dashboard")["view_instance"]
    view._panel._btn_stop.click()

    assert not any(
        "User clicked" in entry.message for entry in view._view_model.log_model.entries
    )
