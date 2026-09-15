"""
Automates Section H ("Known Gaps") of
Tasks/reports/dev_board_user_end_test_cases.md.

These are NOT bug regression tests — they pin down control widgets that
exist in DevBoardPanel.qml's System Controls card but are not yet wired to
DashboardPresenter. Their purpose is to fail loudly the moment someone
starts reading these dropdowns/fields for real, so the change gets
noticed (and this file + the report get updated) instead of silently
drifting out of sync with what the report documents.

BOT-030 Phase 4: these controls moved from ControlCard (QtWidgets) to
DevBoardPanel.qml — still purely decorative (no ViewModel binding at all,
matching their pre-migration "cosmetic only" status), so driving them is a
matter of setting QML item properties directly rather than clicking real
QWidgets.
"""

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest


def _click_toolbar_pill(toolbar, code, qml_item):
    """Real QML click on one of `ChartToolbar`'s `TimeframeToolbar.qml`
    pills (`EPIC-015` Phase 4 — was a QtWidgets `QPushButton`, so this
    replaces `qtbot.mouseClick(toolbar._buttons[code], ...)`)."""
    pill = qml_item(toolbar.root_object, f"timeframePill_{code}")
    assert pill is not None, code
    point = pill.mapToScene(pill.boundingRect().center())
    QTest.mouseClick(
        toolbar.quick_widget, Qt.MouseButton.LeftButton, pos=point.toPoint()
    )


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item=None):
    # Not view._panel._btn_load_history.click(): the button is legitimately
    # disabled while uiMode == "LIVE" (autostart already connected the
    # mocked stream by the time `navigate` returns) — same target the
    # button's own handler calls.
    view._view_model.requestLoadHistory()


def _wait_for_reload_or_restart(qtbot, presenter, action, timeout=3000):
    """
    @brief Waits for `action` to finish settling, whichever background path
    it took.
    @details A timeframe change (or Load History) can resolve through either
    _run_load_history (emits ui_history_reloaded_signal /
    ui_history_load_finished_signal) or, if the FSM is already LIVE (which
    BOT-034 auto-start often leaves it in — navigate() only waits for the
    *first* Start Live attempt to settle, not every later action),
    _run_sync_and_start's stop-then-restart path (emits
    ui_stream_success_signal / ui_stream_failed_signal instead). Waiting on
    only one of these signal families is what made this test flaky —
    whichever path the code didn't take left the test waiting for a signal
    that would never come.
    """
    settled = {"done": False}

    def _mark_settled(*_args) -> None:
        settled["done"] = True

    signals = [
        presenter.ui_history_reloaded_signal,
        presenter.ui_stream_success_signal,
        presenter.ui_stream_failed_signal,
    ]
    for sig in signals:
        sig.connect(_mark_settled)
    try:
        action()
        qtbot.waitUntil(lambda: settled["done"], timeout=timeout)
    finally:
        for sig in signals:
            sig.disconnect(_mark_settled)


def test_symbol_dropdown_changes_which_symbol_load_history_fetches(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-02: FIXED by BOT-033 Phase 2 — choosing "BTCUSDT" in the Symbol
    field now changes which symbol Load History actually fetches (was
    hard-coded to ETHUSDT via `_DEFAULT_SYMBOLS` before this task).

    EPIC-014 replaced the two-item combo this used to drive with the shared
    picker, so the choice is made through the picker's own signal — the same
    path a click on a card takes — rather than by index."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    view._panel._view_model.symbol = "BTCUSDT"
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert presenter._active_symbol == "BTCUSDT"
    assert view.chart_cards[0].symbol == "BTCUSDT"
    assert "BTCUSDT" in presenter.active_charts


def test_market_dropdown_has_no_presenter_effect(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-01: switching Market (Spot/Futures) triggers no presenter
    action at all — there is no binding connected to it."""
    qtbot.addWidget(main_window)
    _, view = _open_dashboard(navigate)

    log_before = list(view._view_model.log_model.entries)
    view._panel._cbo_market.setCurrentIndex(1)  # "Futures"
    qtbot.wait(50)

    assert list(view._view_model.log_model.entries) == log_before


def test_chart_toolbar_timeframe_click_triggers_a_reload(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-03 / TC-GAP-06 — FIXED by BOT-033: clicking "5m" on the
    chart's own toolbar now changes DashboardPresenter._active_interval and
    immediately reloads history with it. The old System Controls
    "Timeframe" dropdown (`cboTimeframe`) was removed entirely — this
    toolbar is the single source of truth now (see BOT-033 task file §6)."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    # BOT-034 auto-start likely already left the FSM at LIVE by the time
    # this test starts (navigate() only waits for the *first* Start Live
    # attempt to settle) — see _wait_for_reload_or_restart's docstring for
    # why that means either action below could take the plain-reload path
    # or the stop-then-restart path.
    _wait_for_reload_or_restart(
        qtbot, presenter, lambda: _click_load_history(view, qml_item)
    )
    assert presenter._active_interval == "1m"
    card = view.chart_cards[0]

    _wait_for_reload_or_restart(
        qtbot, presenter, lambda: _click_toolbar_pill(card.toolbar, "5m", qml_item)
    )

    assert presenter._active_interval == "5m"


def test_reclicking_the_same_timeframe_does_not_reload(
    qtbot, main_window, navigate, qml_item
):
    """Clicking the already-active timeframe must be a no-op — otherwise
    every redundant click would re-fetch history for no reason."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    _wait_for_reload_or_restart(
        qtbot, presenter, lambda: _click_load_history(view, qml_item)
    )
    card = view.chart_cards[0]

    reloaded = []
    presenter.ui_history_reloaded_signal.connect(lambda *a: reloaded.append(1))
    _click_toolbar_pill(card.toolbar, "1m", qml_item)
    qtbot.wait(100)

    assert reloaded == []


def test_strategy_dropdown_arms_the_selected_strategy(qtbot, main_window, navigate):
    """TC-GAP-04: FIXED by `EPIC-023C` — the cosmetic `_cbo_strategy`
    (named a strategy, "SMA Crossover", that was never built) is gone;
    `dev_board_panel.py` now carries a real "Chiến lược" card wired to
    `StrategyArmingCoordinator`, the exact collaborator `TradingPresenter`
    already used. Picking a real registered strategy and clicking "Nạp
    chiến lược" must actually arm it — not just repaint a combo."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    panel = view._panel

    index = panel._cbo_live_strategy.findData("ema_crossover")
    assert index >= 0, "ema_crossover must be a real registered strategy"
    panel._cbo_live_strategy.setCurrentIndex(index)
    # A fresh install has no saved interval yet (`liveInterval` starts as
    # ""), so ArmStrategyCommand would refuse with MISSING_SYMBOL_OR_INTERVAL
    # unless the user picks one — "5m" is deliberately not the combo's own
    # already-showing first entry ("1m"), so this setCurrentText actually
    # changes the selection and fires the signal that reports it to the
    # view model, the same as a real click would.
    panel._cbo_live_interval.setCurrentText("5m")

    qtbot.mouseClick(panel._btn_arm_strategy, Qt.MouseButton.LeftButton)
    qtbot.waitUntil(lambda: presenter._view_model.armedSummary != "", timeout=2000)

    assert presenter._strategy_session.config.strategy_key == "ema_crossover"
    assert panel._lbl_armed_strategy.text() == presenter._view_model.armedSummary


def test_start_date_field_binds_to_the_view_model(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-05: FIXED by BOT-033 Phase 2 — `_txt_start_date` now displays
    `viewModel.startDate` (was a static cosmetic default)."""
    qtbot.addWidget(main_window)
    _, view = _open_dashboard(navigate)

    view._view_model.startDate = "2000-01-01 00:00"
    qtbot.wait(50)

    assert view._panel._txt_start_date.text() == "2000-01-01 00:00"


def test_an_invalid_date_range_blocks_load_history(
    qtbot, main_window, navigate, qml_item, seeded_history
):
    """TC-GAP-05: FIXED by BOT-033 Phase 2 — Start date/End date are
    validated before anything is read; a Start date on/after End date must
    not reach the history store at all.

    `EPIC-025` PR 1.1a's cleanup added the store assertion: "must not reach
    it at all" was in the docstring and in the test's name, and nothing
    checked it — the other two assertions would also hold for a read that
    happened and came back empty. Counted rather than compared to `[]`,
    because opening the screen legitimately reads once before the bad range
    is typed.
    """
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    reads_before_the_bad_range = len(seeded_history.reads)

    view._view_model.startDate = "2024-01-02 00:00"
    view._view_model.endDate = "2024-01-01 00:00"

    reloaded = []
    presenter.ui_history_reloaded_signal.connect(lambda *a: reloaded.append(1))
    _click_load_history(view, qml_item)
    qtbot.wait(100)

    assert reloaded == []
    assert len(seeded_history.reads) == reads_before_the_bad_range
    assert view._view_model.log_model.entries[-1].level == "error"


def test_indicator_checkbox_toggle_has_no_effect_until_next_load(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-07: enabling RSI after Load History already ran does not
    retroactively add it — DashboardPresenter only reads
    script_model.enabled_keys inside _enabled_script_keys, called at Load
    History/Start Live click time, never on a live checklist change. (See
    also test_dev_board_custom_scripts.py for the generic/any-script
    version of this contract.)"""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=2000):
        _click_load_history(view, qml_item)
    assert "rsi_14" not in presenter._script_runner.active

    model = view._view_model.script_model
    rsi_row = next(
        row
        for row in range(model.rowCount())
        if model.data(model.index(row, 0), model.KeyRole) == "rsi_14"
    )
    model.setEnabled(rsi_row, True)
    qtbot.wait(50)

    assert "rsi_14" not in presenter._script_runner.active
    assert not any(
        name.startswith("rsi_14:") for name in view.chart_cards[0].indicators._curves
    )
