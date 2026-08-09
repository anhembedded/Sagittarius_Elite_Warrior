"""
Automates Section D ("Async / Race Condition / Event Ordering") of
Tasks/reports/dev_board_user_end_test_cases.md — the section the user
specifically asked to have deterministically reproduced, not just
described.

Unlike test_dev_board_indicators.py / test_dev_board_known_gaps.py, this
file relies on the app_engine fixture's REAL `IThreadManager`
(ThreadPoolExecutor, see sagittarius_engine/infrastructure/thread_manager.py)
— the races below only exist because background work genuinely overlaps
with the main thread reassigning `DashboardPresenter.active_indicators`.
A synchronous "submit runs immediately" mock (as used elsewhere in this
test suite, e.g. test_dashboard_live_stream.py) would silently make every
one of these tests pass by construction, defeating their purpose.

Root cause (see the report's "Tổng kết & đề xuất hành động" section):
`_run_load_history`/`_compute_indicator_series` read the presenter's
`self.active_indicators` at CALL time, not at submit time, and
`load_history_button` is never disabled while a background load is in
flight (only Start/Stop are gated by the FSM). Two overlapping Load
History clicks therefore feed the same candle data twice into whichever
indicator objects happen to be `self.active_indicators` by the time each
background task gets around to computing.

These are confirmed, NOT-yet-fixed bugs — marked `xfail(strict=True)` so:
  - today, they document the exact reproduction and count as "expected
    failures" instead of breaking the green test suite;
  - the moment someone fixes the underlying race, the test starts
    unexpectedly PASSING, which `strict=True` turns into a hard failure —
    a forcing function to come back and delete the xfail marker (and
    update the report) instead of the fix going unnoticed.

BOT-030 Phase 4: Load History is now a QML button (DevBoardPanel.qml) and
RSI's enabled/period toggles live on DashboardQmlViewModel
(view._view_model) instead of ControlCard/IndicatorControlCard widgets.
"""

import time

from Binace_Bot.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def _click_load_history(view, qml_item):
    root = view.quick_widget.rootObject()
    qml_item(root, "btnLoadHistory").clicked.emit()


def _slow_down_history_queries(monkeypatch, presenter, delay_seconds: float) -> None:
    """
    Widens the race window so two overlapping Load History clicks reliably
    interleave instead of (by sheer luck) fully serializing on a fast
    local machine — mirrors a real DB query taking noticeably longer than
    the near-instant `sig_load_clicked` handler that reassigns
    `active_indicators` on the main thread.
    """
    original_dispatch = presenter.dispatcher.dispatch

    def slow_dispatch(command_type, command_obj):
        if command_type is GetHistoricalKlinesQuery:
            time.sleep(delay_seconds)
        return original_dispatch(command_type, command_obj)

    monkeypatch.setattr(presenter.dispatcher, "dispatch", slow_dispatch)


def test_load_history_button_is_disabled_during_background_load(
    qtbot, main_window, navigate, qml_item
):
    """
    TC-ASY-01 guard: a background history query owns a configuration snapshot,
    so QML disables every incompatible Dev Board action until it completes.
    """
    qtbot.addWidget(main_window)
    _, view = _open_dashboard(navigate)
    root = view.quick_widget.rootObject()

    _click_load_history(view, qml_item)
    assert qml_item(root, "btnLoadHistory").property("enabled") is False


def test_concurrent_load_history_clicks_keep_indicator_series_correct(
    qtbot, main_window, monkeypatch, navigate, qml_item
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    # period=2 (the minimum) so 5 mock candles produce readings (unlike the
    # default period=14, which would just stay empty either way and hide
    # the corruption instead of exposing it).
    view._view_model.rsiEnabled = True
    view._view_model.rsiPeriod = 2
    _slow_down_history_queries(monkeypatch, presenter, delay_seconds=0.05)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=3000):
        _click_load_history(view, qml_item)
        _click_load_history(view, qml_item)

    # Correct behavior: 5 candles at RSI period=2 warm up after 2 candles,
    # producing exactly 3 readings — regardless of how many times the user
    # clicked, since each click is supposed to start clean.
    rsi = presenter.active_indicators["RSI(2)"]
    assert len(rsi.y_data) == 3


def test_four_rapid_load_history_clicks_keep_indicator_series_correct(
    qtbot, main_window, monkeypatch, navigate, qml_item
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    view._view_model.rsiEnabled = True
    view._view_model.rsiPeriod = 2
    _slow_down_history_queries(monkeypatch, presenter, delay_seconds=0.05)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=4000):
        for _ in range(4):
            _click_load_history(view, qml_item)

    rsi = presenter.active_indicators["RSI(2)"]
    assert len(rsi.y_data) == 3


def test_duplicate_closed_tick_for_same_timestamp_appends_twice(
    qtbot, main_window, navigate, qml_item
):
    """
    TC-ASY-10: MarketTickEvent delivering `is_closed=True` twice for the
    same candle (e.g. a WebSocket reconnect re-sending the last closed
    kline) is appended as two separate bars — chart_card.py has no
    timestamp-monotonicity/dedupe guard on append_closed_candle. This is
    NOT marked xfail: it is current, real, and cheap to keep as a living
    "this still doesn't dedupe" tripwire rather than a race needing exact
    timing, so it stays a plain (currently passing-as-documented) test.
    Flip this to assert a length of 1 (and drop this docstring's caveat)
    once dedupe is added.
    """
    from datetime import datetime, timezone

    from Binace_Bot.src.domain.entities.market_data import MarketData
    from Binace_Bot.src.domain.events.market_tick_event import MarketTickEvent

    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)
    card = view.chart_cards[0]
    history_before = len(card._raw_history)

    closed_tick = MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=datetime(2024, 1, 1, 2, 0, tzinfo=timezone.utc),
        open_price=300.0,
        high_price=301.0,
        low_price=299.0,
        close_price=300.5,
        volume=5.0,
        close_time=datetime(2024, 1, 1, 2, 1, tzinfo=timezone.utc),
        quote_asset_volume=1500.0,
        number_of_trades=3,
        taker_buy_base_asset_volume=2.0,
        taker_buy_quote_asset_volume=600.0,
        is_closed=True,
    )

    with qtbot.waitSignal(presenter.ui_chart_update_signal, timeout=2000):
        presenter._handle_market_tick(MarketTickEvent(market_data=closed_tick))
    with qtbot.waitSignal(presenter.ui_chart_update_signal, timeout=2000):
        presenter._handle_market_tick(MarketTickEvent(market_data=closed_tick))

    # Documents the current gap: both deliveries land as separate bars.
    assert len(card._raw_history) == history_before + 2
