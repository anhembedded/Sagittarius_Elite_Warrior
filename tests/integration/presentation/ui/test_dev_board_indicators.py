"""
Automates Section B ("Indicators") of
Tasks/reports/dev_board_user_end_test_cases.md. Each test docstring cites
its TC-IND-## id so the two documents stay traceable to each other.

BOT-032 Phase 6: RSI/EMA/MACD are no longer hardcoded — rsi_14/ema_20/
ema_50/ema_100/ema_200/macd_full are ordinary registered scripts (see
binance_bot_module.py), driven through the same "CUSTOM SCRIPTS" checklist
(now just called "INDICATORS") as any user-authored script. Enabling/
disabling goes through view._view_model.script_model, not a per-indicator
Property — see test_dev_board_custom_scripts.py for the checklist/Repeater
wiring itself; this file only pins down that the *default* indicators are
wired correctly.

conftest.MOCK_KLINE_COUNT is 5 — too few to warm up RSI(14)/EMA(20+)/MACD
(needs 14/20/35 bars respectively), so these tests synchronize on
ui_script_region_signal (fires every bar regardless of warm-up, see
IndicatorScriptRunner.feed()) rather than ui_indicator_data_signal, and
assert against presenter._script_runner.active rather than rendered curves
— curve rendering with properly warmed-up data is already covered in
test_indicator_script_runner.py/test_chart_card.py.
"""


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item):
    root = view.quick_widget.rootObject()
    qml_item(root, "btnLoadHistory").clicked.emit()


def test_ema_20_50_100_200_are_pre_enabled_by_default(qtbot, main_window, navigate):
    """US-07: "no indicator hardcoded in the engine, default is EMA
    200/100/50/20" — these four must already be checked the first time the
    Dev Board opens, with no user action."""
    qtbot.addWidget(main_window)
    _presenter, view = _open_dashboard(navigate)

    enabled = set(view._view_model.script_model.enabled_keys)

    assert {"ema_20", "ema_50", "ema_100", "ema_200"} <= enabled


def test_rsi_and_macd_are_not_pre_enabled(qtbot, main_window, navigate):
    """Only the EMAs are called out as defaults in US-07 — RSI/MACD stay
    opt-in, same as every other registered script."""
    qtbot.addWidget(main_window)
    _presenter, view = _open_dashboard(navigate)

    enabled = set(view._view_model.script_model.enabled_keys)

    assert "rsi_14" not in enabled
    assert "macd_full" not in enabled


def test_rsi_14_registers_as_a_subplot_script(qtbot, main_window, navigate, qml_item):
    """TC-IND-01: RSI must be a subplot script, not drawn on the main
    price plot."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.script_model.setEnabled(_row_index(view, "rsi_14"), True)

    with qtbot.waitSignal(presenter.ui_script_region_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert presenter._script_runner.active["rsi_14"].overlay is False


def test_ema_registers_as_overlay_not_subplot(qtbot, main_window, navigate, qml_item):
    """TC-IND-02: EMA must be drawn on the main price plot, not its own
    subplot row. ema_20 is pre-enabled (US-07), so no toggle needed."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_script_region_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert presenter._script_runner.active["ema_20"].overlay is True


def test_all_default_scripts_together_no_key_collisions(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-04: RSI+EMA(x4)+MACD together must all register under their
    own distinct keys — no overwriting each other."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    for key in ("rsi_14", "macd_full"):
        view._view_model.script_model.setEnabled(_row_index(view, key), True)

    with qtbot.waitSignal(presenter.ui_script_region_signal, timeout=2000):
        _click_load_history(view, qml_item)

    active = presenter._script_runner.active
    assert set(active) >= {
        "rsi_14",
        "macd_full",
        "ema_20",
        "ema_50",
        "ema_100",
        "ema_200",
    }
    assert active["ema_20"].overlay is True
    assert active["rsi_14"].overlay is False
    assert active["macd_full"].overlay is False


def test_repeated_load_history_keeps_exactly_one_registration_per_script(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-07: clicking "Load History" 3 times in a row with the same
    scripts enabled must leave exactly one ActiveScript per key — the
    original bug this pinned down ("start nhieu lan no bi loi nay") was
    about duplicate curves, which rebuild() structurally can't produce
    anymore (it always replaces `active` with a fresh dict) — this proves
    the rebuild itself doesn't raise or drop keys across repeats."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    for _ in range(3):
        # ui_history_load_finished_signal always fires (unconditional
        # `finally` in _run_load_history) and is what resets historyLoading
        # back to False — the most reliable point to synchronize repeated
        # clicks on, unlike ui_history_reloaded_signal which some of this
        # suite's other tests have found racy under real ThreadPoolExecutor
        # scheduling (see BOT-032 task file's Phase 5 notes).
        with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=2000):
            _click_load_history(view, qml_item)

    active = presenter._script_runner.active
    assert set(active) == {"ema_20", "ema_50", "ema_100", "ema_200"}


def test_macd_produces_no_series_with_too_little_history(
    qtbot, main_window, navigate, qml_item
):
    """TC-IND-11: MACD needs 26+9 closes to warm up; with only 5 mock
    candles (see conftest.MOCK_KLINE_COUNT) it must produce nothing — no
    NaN/garbage point should reach the chart."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.script_model.setEnabled(_row_index(view, "macd_full"), True)

    with qtbot.waitSignal(presenter.ui_script_region_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert presenter._script_runner.active["macd_full"].series == {}


def _row_index(view, key: str) -> int:
    model = view._view_model.script_model
    keys = [
        model.data(model.index(row, 0), model.KeyRole)
        for row in range(model.rowCount())
    ]
    return keys.index(key)
