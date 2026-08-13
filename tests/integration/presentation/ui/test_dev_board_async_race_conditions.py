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

Original root cause (see the report's "Tổng kết & đề xuất hành động"
section): `_run_load_history`/`IndicatorScriptRunner.feed_all` read the
presenter's `self._script_runner.active` at CALL time, not at submit
time, and `load_history_button` was never disabled while a background
load was in flight (only Start/Stop were gated by the FSM). Two
overlapping Load History clicks therefore fed the same candle data twice
into whichever script instances happened to be `active` by the time each
background task got around to computing.

BOT-027 ✅ FIXED — these tests now pin the CORRECT behavior (they were
`xfail` while the bug was live; renamed from `..._corrupt_indicator_series`
to `..._keep_indicator_series_correct` when the fix landed). The guard is
in `StreamLifecycleController._on_load_history()`/`._on_start_stream()`:
both check `self._view_model.historyLoading` and `self.fsm.current_state`
at the top and return early, so overlapping runs can no longer be
submitted at all — covering TC-ASY-01/03/04. Keep these tests on the REAL
thread manager (see above): a synchronous `submit` mock would make them
pass by construction and stop guarding the regression.

BOT-032 Phase 6: RSI/EMA/MACD are ordinary registered scripts now (no
`rsiEnabled`/`rsiPeriod` on the ViewModel to force a fast-warming period —
scripts take no runtime parameters) — these tests use `ema_cross`
(EMA 12/26) with a monkeypatched synthetic kline response long enough to
warm it up, instead of overriding conftest.MOCK_KLINE_COUNT globally.

BOT-030 Phase 4: Load History is now a QML button (DevBoardPanel.qml) and
script enablement lives on DashboardQmlViewModel.script_model
(view._view_model) instead of ControlCard/IndicatorControlCard widgets.
"""

import time
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData


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


def _use_synthetic_klines(monkeypatch, presenter, count: int) -> None:
    """
    @brief Makes the mocked dispatcher return `count` synthetic candles for
    GetHistoricalKlinesQuery instead of conftest's fixed 5.
    @details Needed because fixed-period default scripts (BOT-032 Phase 6)
    can't be parametrized down to a fast-warming period the way the old
    hardcoded `RSI(period=2)` override could — ema_cross needs 26 bars to
    warm up its slow EMA, more than MOCK_KLINE_COUNT provides. Composes with
    `_slow_down_history_queries` regardless of call order — both capture
    whatever `presenter.dispatcher.dispatch` currently is and wrap it.
    """
    base_time = datetime(2024, 1, 1, tzinfo=UTC)
    klines = []
    for i in range(count):
        open_time = base_time + timedelta(minutes=i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
                symbol="ETHUSDT",
                interval="1m",
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
    klines.reverse()  # newest-first, matching the real repository's contract

    original_dispatch = presenter.dispatcher.dispatch

    def dispatch_with_synthetic_klines(command_type, command_obj):
        if command_type is GetHistoricalKlinesQuery:
            response = MagicMock()
            response.success = True
            # GetHistoricalKlinesQueryHandler's contract: `symbol` as a list
            # (StreamLifecycleController always sends one) returns
            # {symbol: klines}, not a flat list — see conftest.mock_dispatch's
            # comment for why a flat list here makes _run_load_history's
            # `isinstance(results, dict)` guard return before ever reaching
            # `_script_runner.feed_all()`.
            if isinstance(command_obj.symbol, list):
                response.data = {sym: klines for sym in command_obj.symbol}
            else:
                response.data = klines
            return response
        return original_dispatch(command_type, command_obj)

    monkeypatch.setattr(
        presenter.dispatcher, "dispatch", dispatch_with_synthetic_klines
    )


def _enable_script(view, key: str) -> None:
    model = view._view_model.script_model
    row = next(
        r
        for r in range(model.rowCount())
        if model.data(model.index(r, 0), model.KeyRole) == key
    )
    model.setEnabled(row, True)


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
    _enable_script(view, "ema_cross")
    # 40 synthetic candles so EMA 26 (the slower of the pair) actually warms
    # up — see _use_synthetic_klines' docstring for why this replaces the
    # old RSI(period=2) trick.
    _use_synthetic_klines(monkeypatch, presenter, count=40)
    _slow_down_history_queries(monkeypatch, presenter, delay_seconds=0.05)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=3000):
        _click_load_history(view, qml_item)
        _click_load_history(view, qml_item)

    # Correct behavior: each click is supposed to start clean, so no line's
    # timestamp series should ever contain a duplicate — a duplicate is
    # exactly what "the same candle batch got fed into two different script
    # instances that got merged" would produce.
    x_data, y_data = presenter._script_runner.active["ema_cross"].series["EMA 12"]
    assert y_data, "expected EMA 12 to have actually warmed up"
    assert len(x_data) == len(set(x_data))


def test_four_rapid_load_history_clicks_keep_indicator_series_correct(
    qtbot, main_window, monkeypatch, navigate, qml_item
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _enable_script(view, "ema_cross")
    _use_synthetic_klines(monkeypatch, presenter, count=40)
    _slow_down_history_queries(monkeypatch, presenter, delay_seconds=0.05)

    with qtbot.waitSignal(presenter.ui_history_load_finished_signal, timeout=4000):
        for _ in range(4):
            _click_load_history(view, qml_item)

    x_data, y_data = presenter._script_runner.active["ema_cross"].series["EMA 12"]
    assert y_data, "expected EMA 12 to have actually warmed up"
    assert len(x_data) == len(set(x_data))


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
    from datetime import datetime

    from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData
    from Sagittarius_Elite_Warrior.src.domain.events.market_tick_event import (
        MarketTickEvent,
    )

    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)

    with qtbot.waitSignal(presenter.ui_history_reloaded_signal, timeout=2000):
        _click_load_history(view, qml_item)
    card = view.chart_cards[0]
    history_before = len(card._raw_history)

    closed_tick = MarketData(
        symbol="ETHUSDT",
        interval="1m",
        open_time=datetime(2024, 1, 1, 2, 0, tzinfo=UTC),
        open_price=300.0,
        high_price=301.0,
        low_price=299.0,
        close_price=300.5,
        volume=5.0,
        close_time=datetime(2024, 1, 1, 2, 1, tzinfo=UTC),
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
