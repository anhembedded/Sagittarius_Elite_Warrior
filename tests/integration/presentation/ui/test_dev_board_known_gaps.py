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


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item):
    root = view.quick_widget.rootObject()
    qml_item(root, "btnLoadHistory").clicked.emit()


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
    """TC-GAP-02: FIXED by BOT-033 Phase 2 — picking "BTCUSDT" from the
    Symbol dropdown now changes which symbol Load History actually fetches
    (was hard-coded to ETHUSDT via `_DEFAULT_SYMBOLS` before this task).
    Driven via `currentIndex` (a plain property whose notify signal
    `onCurrentTextChanged` is wired regardless of how it changed), not
    `editText` — an editable ComboBox's `editText` only feeds `currentText`
    on a real Return/focus-out, which `setProperty` cannot simulate."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    qml_item(root, "cboSymbol").setProperty("currentIndex", 0)  # "BTCUSDT"
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
    root = view.quick_widget.rootObject()

    log_before = list(view._view_model.log_model.entries)
    qml_item(root, "cboMarket").setProperty("currentIndex", 1)  # "Futures"
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

    btn_5m = card.toolbar._buttons["5m"]
    _wait_for_reload_or_restart(
        qtbot, presenter, lambda: qtbot.mouseClick(btn_5m, Qt.LeftButton)
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
    qtbot.mouseClick(card.toolbar._buttons["1m"], Qt.LeftButton)
    qtbot.wait(100)

    assert reloaded == []


def test_strategy_dropdown_has_no_presenter_effect(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-04: Strategy dropdown is cosmetic today — out of Phase 2's
    scope (needs a concrete strategy + signal/marker plumbing, see
    BOT-026), unlike Symbol/Start date/End date which Phase 2 fixed."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    qml_item(root, "cboStrategy").setProperty("currentIndex", 1)  # "SMA Crossover"

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    # conftest.MOCK_KLINE_COUNT mock candles come back regardless of the
    # (ignored) strategy selection.
    assert len(view.chart_cards[0]._raw_history) == 5


def test_start_date_field_binds_to_the_view_model(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-05: FIXED by BOT-033 Phase 2 — txtStartDate now displays
    viewModel.startDate (was a static `Qt.formatDateTime(...)` cosmetic
    default). Setting the ViewModel from Python — the same thing
    `onTextEdited` does for a real keystroke, which `setProperty("text", ...)`
    cannot simulate (TextField.textEdited only fires from actual editing,
    not a programmatic `text` assignment) — must show up in the rendered
    QML item."""
    qtbot.addWidget(main_window)
    _, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    view._view_model.startDate = "2000-01-01 00:00"
    qtbot.wait(50)

    assert qml_item(root, "txtStartDate").property("text") == "2000-01-01 00:00"


def test_an_invalid_date_range_blocks_load_history(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-05: FIXED by BOT-033 Phase 2 — Start date/End date are now
    validated before dispatch; a Start date on/after End date must not
    reach GetHistoricalKlinesQuery at all."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    view._view_model.startDate = "2024-01-02 00:00"
    view._view_model.endDate = "2024-01-01 00:00"

    reloaded = []
    presenter.ui_history_reloaded_signal.connect(lambda *a: reloaded.append(1))
    _click_load_history(view, qml_item)
    qtbot.wait(100)

    assert reloaded == []
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
