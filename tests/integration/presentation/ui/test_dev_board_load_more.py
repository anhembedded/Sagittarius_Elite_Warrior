"""
BOT-035 — load more historical candles when the user scrolls/pans near the
left edge of the chart.

conftest's mocked dispatch always returns the same fixed 5-candle batch
regardless of query params (it never looks at end_time), which can't tell
"initial load" apart from "load more" — every test here installs its own
dispatch override (via `monkeypatch`, auto-reverted) that returns an OLDER
batch specifically when GetHistoricalKlinesQuery.end_time is set, mirroring
what the real repository does.

Simulates the "user scrolled near the edge" trigger by emitting
ChartCard.sig_near_left_edge directly rather than a real drag gesture — this
repo has no existing precedent for simulating a pyqtgraph mouse-drag pan
(only QPushButton/QML clicks), and EdgeScrollDetector's own unit tests
already cover the pan-distance math in isolation.

MOCK_KLINE_COUNT/build_mock_klines are duplicated from conftest.py rather
than imported — this directory's test modules have no __init__.py, so
they're collected as top-level modules, not a package (a relative
`from .conftest import` fails at collection). Same workaround already used
by test_sanity_ui_e2e.py.
"""

from datetime import UTC, datetime, timedelta

from Sagittarius_Elite_Warrior.src.application.use_cases.queries.get_historical_klines.query import (
    GetHistoricalKlinesQuery,
)
from Sagittarius_Elite_Warrior.src.domain.entities.market_data import MarketData

MOCK_KLINE_COUNT = 5
_BASE_TIME = datetime(2024, 1, 1, tzinfo=UTC)


def _build_mock_klines(symbol: str, interval: str = "1m") -> list[MarketData]:
    """Must match conftest.build_mock_klines exactly — this is what the
    normal (non-load-more) dispatch path returns."""
    klines = []
    for i in range(MOCK_KLINE_COUNT):
        open_time = _BASE_TIME + timedelta(minutes=i)
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


def _older_mock_klines(symbol: str) -> list[MarketData]:
    """Newest-first, all strictly older than build_mock_klines()'s oldest
    candle (whose close_time is _BASE_TIME + 1 minute)."""
    klines = []
    for i in range(MOCK_KLINE_COUNT):
        open_time = _BASE_TIME - timedelta(minutes=MOCK_KLINE_COUNT - i)
        close_time = open_time + timedelta(minutes=1)
        klines.append(
            MarketData(
                symbol=symbol,
                interval="1m",
                open_time=open_time,
                open_price=90.0 + i,
                high_price=91.0 + i,
                low_price=89.0 + i,
                close_price=90.5 + i,
                volume=5.0,
                close_time=close_time,
                quote_asset_volume=500.0,
                number_of_trades=3,
                taker_buy_base_asset_volume=2.5,
                taker_buy_quote_asset_volume=250.0,
            )
        )
    klines.reverse()
    return klines


def _install_load_more_capable_dispatch(monkeypatch, presenter):
    """Replaces presenter.dispatcher.dispatch with one that returns an OLDER
    batch specifically for a load-more query (end_time set), and the normal
    fixed batch otherwise — real GetKlinesHistoricalQuery handler behavior,
    just without a real database."""

    def dispatch(command_type, command_obj):
        from unittest.mock import MagicMock

        response = MagicMock()
        response.success = True
        if command_type is GetHistoricalKlinesQuery:
            if command_obj.end_time is not None:
                response.data = _older_mock_klines(command_obj.symbol)
            else:
                response.data = _build_mock_klines(command_obj.symbol)
        else:
            response.data = []
        return response

    monkeypatch.setattr(presenter.dispatcher, "dispatch", dispatch)


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def test_scrolling_near_the_left_edge_prepends_older_candles(
    qtbot, main_window, navigate, monkeypatch
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _install_load_more_capable_dispatch(monkeypatch, presenter)
    card = view.chart_cards[0]
    history_before = len(card._raw_history)
    oldest_before = card._raw_history[0][0]

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert len(card._raw_history) == history_before + MOCK_KLINE_COUNT
    assert card._raw_history[0][0] < oldest_before


def test_load_more_does_not_reset_the_current_viewport(
    qtbot, main_window, navigate, monkeypatch
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _install_load_more_capable_dispatch(monkeypatch, presenter)
    card = view.chart_cards[0]
    card.plot_layout.main_plot.setXRange(
        card._raw_history[0][0], card._raw_history[-1][0], padding=0
    )
    view_before = card.plot_layout.main_plot.vb.viewRange()

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert card.plot_layout.main_plot.vb.viewRange() == view_before


def test_load_more_rebuilds_scripts_without_dropping_the_active_set(
    qtbot, main_window, navigate, monkeypatch
):
    """A prepend forces IndicatorScriptRunner.rebuild() (see
    dashboard_presenter._on_history_prepended's docstring) — the set of
    enabled scripts must come out the other side unchanged."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _install_load_more_capable_dispatch(monkeypatch, presenter)
    card = view.chart_cards[0]
    active_before = set(presenter._script_runner.active)

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert set(presenter._script_runner.active) == active_before


def test_a_second_edge_signal_before_the_first_settles_does_not_double_fetch(
    qtbot, main_window, navigate, monkeypatch
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _install_load_more_capable_dispatch(monkeypatch, presenter)
    card = view.chart_cards[0]

    calls = []
    original_submit = presenter._thread_manager.submit

    def counting_submit(task, *args, **kwargs):
        if task == presenter._run_load_more_history:
            calls.append(1)
        return original_submit(task, *args, **kwargs)

    monkeypatch.setattr(presenter._thread_manager, "submit", counting_submit)

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)
        card.sig_near_left_edge.emit(card.symbol)
        card.sig_near_left_edge.emit(card.symbol)

    assert len(calls) == 1
