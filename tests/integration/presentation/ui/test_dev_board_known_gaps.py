"""
Automates Section H ("Known Gaps") of
Tasks/reports/dev_board_user_end_test_cases.md.

These are NOT bug regression tests — they pin down control widgets that
exist in ControlCard/ChartToolbar/IndicatorControlCard but are not yet
wired to DashboardPresenter. Their purpose is to fail loudly the moment
someone starts reading these dropdowns/buttons for real, so the change
gets noticed (and this file + the report get updated) instead of silently
drifting out of sync with what the report documents.
"""

from PySide6.QtCore import Qt


def _open_dashboard(qtbot, main_window):
    btn_dashboard = main_window._sidebar._buttons["dashboard"]
    qtbot.mouseClick(btn_dashboard, Qt.LeftButton)
    cfg = main_window._router._registry["dashboard"]
    return cfg["presenter_instance"], cfg["view_instance"]


def test_symbol_dropdown_does_not_change_loaded_symbol(qtbot, main_window):
    """TC-GAP-02: selecting BTCUSDT in the Symbol dropdown must not change
    which symbol Load History actually fetches — it is hard-coded to
    ETHUSDT (`_DEFAULT_SYMBOLS`) today."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(qtbot, main_window)

    view.control_card.symbol_dropdown.setCurrentText("BTCUSDT")
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    assert view.chart_cards[0].symbol == "ETHUSDT"
    assert "BTCUSDT" not in presenter.active_charts


def test_market_dropdown_has_no_presenter_effect(qtbot, main_window):
    """TC-GAP-01: switching Market (Spot/Futures) triggers no presenter
    action at all — there is no signal connected to it."""
    qtbot.addWidget(main_window)
    _, view = _open_dashboard(qtbot, main_window)

    log_before = view.monitor_card.text_edit.toPlainText()
    view.control_card.market_dropdown.setCurrentText("Futures")
    qtbot.wait(50)

    assert view.monitor_card.text_edit.toPlainText() == log_before


def test_control_card_timeframe_dropdown_does_not_change_interval(qtbot, main_window):
    """TC-GAP-03: the System Controls "Timeframe" dropdown is not read
    anywhere — Load History always requests the hard-coded "1m" interval."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(qtbot, main_window)

    view.control_card.timeframe_dropdown.setCurrentText("1h")
    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    # No direct getter for the interval used, but a successful reload with
    # the dropdown on "1h" proves the click path never raised on/consulted
    # it — combined with the source-level grep in the report (zero reads of
    # `timeframe_dropdown`), this pins down the current no-op behavior.
    assert view.chart_cards[0]._raw_history  # reload still succeeded, ignoring "1h"


def test_chart_toolbar_timeframe_click_only_changes_highlight(qtbot, main_window):
    """TC-GAP-06 / TC-CHT-11: clicking "5m" on the chart's own toolbar only
    updates which button looks active — ChartToolbar.sig_timeframe_changed
    is never connected to the presenter, so no data changes."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(qtbot, main_window)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)
    card = view.chart_cards[0]
    history_before = list(card._raw_history)

    btn_5m = card.toolbar._buttons["5m"]
    qtbot.mouseClick(btn_5m, Qt.LeftButton)
    qtbot.wait(50)

    assert card._raw_history == history_before


def test_strategy_and_date_pickers_have_no_presenter_effect(qtbot, main_window):
    """TC-GAP-04 / TC-GAP-05: Strategy dropdown and Start/End date pickers
    are cosmetic today — GetHistoricalKlinesQuery always uses a fixed
    `limit=5000`, never a date range, and Strategy is never read."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(qtbot, main_window)

    view.control_card.strategy_dropdown.setCurrentText("SMA Crossover")
    original_start = view.control_card.start_date_picker.dateTime()
    view.control_card.start_date_picker.setDateTime(original_start.addDays(-365))

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)

    # conftest.MOCK_KLINE_COUNT mock candles come back regardless of the
    # (ignored) 365-day-wider date range or the (ignored) strategy selection.
    assert len(view.chart_cards[0]._raw_history) == 5


def test_indicator_checkbox_toggle_has_no_effect_until_next_load(qtbot, main_window):
    """TC-GAP-07: ticking RSI after Load History already ran does not
    retroactively add it — there is no toggled/stateChanged connection on
    chk_rsi/chk_ema/chk_macd."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(qtbot, main_window)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        qtbot.mouseClick(view.control_card.load_history_button, Qt.LeftButton)
    assert presenter.active_indicators == {}

    view.indicator_control_card.chk_rsi.setChecked(True)
    qtbot.wait(50)

    assert presenter.active_indicators == {}
    assert "RSI(14)" not in view.chart_cards[0].indicators._curves
