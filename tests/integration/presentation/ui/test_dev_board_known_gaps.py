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


def test_symbol_dropdown_does_not_change_loaded_symbol(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-02: selecting BTCUSDT in the Symbol dropdown must not change
    which symbol Load History actually fetches — it is hard-coded to
    ETHUSDT (`_DEFAULT_SYMBOLS`) today."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    qml_item(root, "cboSymbol").setProperty("editText", "BTCUSDT")
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    assert view.chart_cards[0].symbol == "ETHUSDT"
    assert "BTCUSDT" not in presenter.active_charts


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

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)
    assert presenter._active_interval == "1m"
    card = view.chart_cards[0]

    btn_5m = card.toolbar._buttons["5m"]
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(btn_5m, Qt.LeftButton)

    assert presenter._active_interval == "5m"


def test_reclicking_the_same_timeframe_does_not_reload(
    qtbot, main_window, navigate, qml_item
):
    """Clicking the already-active timeframe must be a no-op — otherwise
    every redundant click would re-fetch history for no reason."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)
    card = view.chart_cards[0]

    reloaded = []
    presenter.ui_history_reloaded_signal.connect(lambda *a: reloaded.append(1))
    qtbot.mouseClick(card.toolbar._buttons["1m"], Qt.LeftButton)
    qtbot.wait(100)

    assert reloaded == []


def test_strategy_and_date_fields_have_no_presenter_effect(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-04 / TC-GAP-05: Strategy dropdown and Start/End date fields
    are cosmetic today — GetHistoricalKlinesQuery always uses a fixed
    `limit=5000`, never a date range, and Strategy is never read."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    qml_item(root, "cboStrategy").setProperty("currentIndex", 1)  # "SMA Crossover"
    qml_item(root, "txtStartDate").setProperty("text", "2000-01-01 00:00")

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)

    # conftest.MOCK_KLINE_COUNT mock candles come back regardless of the
    # (ignored) far-past start date or the (ignored) strategy selection.
    assert len(view.chart_cards[0]._raw_history) == 5


def test_indicator_checkbox_toggle_has_no_effect_until_next_load(
    qtbot, main_window, navigate, qml_item
):
    """TC-GAP-07: enabling RSI after Load History already ran does not
    retroactively add it — DashboardPresenter only reads
    view_model.rsiEnabled inside _build_active_indicators, called at
    Load History/Start Live click time, never on a live property change."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)
    assert presenter.active_indicators == {}

    view._view_model.rsiEnabled = True
    qtbot.wait(50)

    assert presenter.active_indicators == {}
    assert "RSI(14)" not in view.chart_cards[0].indicators._curves
