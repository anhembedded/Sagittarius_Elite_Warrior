"""
BOT-032 Phase 3 — the indicator checklist in DevBoardPanel.qml (originally
"CUSTOM SCRIPTS"; since Phase 6 it's the ONLY indicator checklist — RSI/EMA/
MACD are registered scripts too, see test_dev_board_indicators.py).

Mirrors test_dev_board_known_gaps.py's style: toggles go through the
ViewModel directly (view._view_model.script_model.setEnabled(...)) rather
than simulating a real QML mouse click — there is no existing precedent in
this repo for clicking a QML CheckBox (only QtWidgets buttons), so this file
doesn't invent one.

What IS specific to this file: the checklist is built by a Repeater bound to
a QAbstractListModel (IndicatorScriptRegistry.available() at runtime), not a
handful of hand-written StyledCheck instances — so there is a real risk
(flagged in the BOT-032 task file) that the Repeater/role-binding wiring
itself is broken even if the underlying model is fine. That risk is covered
by test_custom_scripts_checklist_renders_every_registered_script, which
walks the real QML visual tree with qml_item — Repeater delegates are NOT
QObject children, so requires walk_qml_items/qml_item, not findChild().
"""


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item):
    root = view.quick_widget.rootObject()
    qml_item(root, "btnLoadHistory").clicked.emit()


def test_custom_scripts_checklist_renders_every_registered_script(
    qtbot, main_window, navigate, qml_item
):
    """The Repeater must produce one checkbox per script the real
    IndicatorScriptRegistry knows about, each carrying the script's own
    title — not a stale/hardcoded list."""
    qtbot.addWidget(main_window)
    _presenter, view = _open_dashboard(navigate)

    from Sagittarius_Elite_Warrior.src.application.services.indicator_script_registry import (
        IndicatorScriptRegistry,
    )

    registry = main_window._app.context.container.resolve(IndicatorScriptRegistry)
    root = view.quick_widget.rootObject()

    for key, script_cls in registry.available().items():
        checkbox = qml_item(root, f"chkScript_{key}")
        assert checkbox is not None, f"no checkbox rendered for script {key!r}"
        assert checkbox.property("text") == script_cls.title
        # default_enabled scripts (BOT-032 Phase 6 — e.g. ema_20/50/100/200)
        # start pre-checked; every other script starts opted-out.
        expected_checked = getattr(script_cls, "default_enabled", False)
        assert checkbox.property("checked") is expected_checked


def test_enabling_a_script_then_load_history_registers_it_as_active(
    qtbot, main_window, navigate, qml_item
):
    """Enabling ema_ribbon through the list model, then Load History, must
    make the Presenter actually run it — proving the checklist → ViewModel →
    _enabled_script_keys() → IndicatorScriptRunner.rebuild() wiring holds
    end-to-end in the real app.

    Doesn't assert a curve appears: ema_ribbon's fastest line is EMA(20),
    which needs 20 bars to warm up, but conftest.MOCK_KLINE_COUNT is 5 (same
    constraint test_dev_board_indicators.py's MACD warm-up test documents) —
    ui_indicator_data_signal never fires for a script line under warm-up (see
    BaseIndicatorScript.plot(): a None value isn't entered into the buffer at
    all, so compute() has nothing to emit). Curve rendering itself is already
    covered with properly warmed-up synthetic data in
    test_indicator_script_runner.py/test_chart_card.py.

    Synchronizes on ui_history_load_finished_signal (fires exactly once per
    _run_load_history call) rather than ui_script_region_signal — the latter
    fires once per bar per active script, which can burst multiple times in
    quick succession from a background thread and race
    qtbot.waitSignal()'s single-shot disconnect (Qt does not retroactively
    cancel already-posted queued events for a cross-thread signal emission
    once disconnected) — a real, reproduced Windows access violation, not a
    hypothetical one. See test_dev_board_indicators.py's module docstring
    for the full bisection.
    """
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    script_model = view._view_model.script_model
    row = _row_index(script_model, "ema_ribbon")
    script_model.setEnabled(row, True)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert "ema_ribbon" in presenter._script_runner.active


def test_unchecking_a_script_stops_it_from_running_on_the_next_load(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-07 parity: toggling off must take effect on the NEXT Load
    History, not retroactively remove what's already drawn."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    script_model = view._view_model.script_model
    row = _row_index(script_model, "ema_ribbon")
    script_model.setEnabled(row, True)
    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=2000):
        _click_load_history(view, qml_item)
    assert "ema_ribbon" in presenter._script_runner.active

    script_model.setEnabled(row, False)
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert "ema_ribbon" not in presenter._script_runner.active


def _row_keys(script_model):
    return [
        script_model.data(script_model.index(row, 0), script_model.KeyRole)
        for row in range(script_model.rowCount())
    ]


def _row_index(script_model, key: str) -> int:
    return _row_keys(script_model).index(key)
