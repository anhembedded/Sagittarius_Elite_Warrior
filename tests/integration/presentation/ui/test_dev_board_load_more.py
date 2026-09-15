"""
BOT-035 — load more historical candles when the user scrolls/pans near the
left edge of the chart.

`EPIC-025` PR 1.1a removed the hand-rolled dispatcher these tests used to
install. The history read is `IHistoricalKlines` now, and its fake is a real
store that honours `end_time` — so "initial load" and "load more" tell
themselves apart, and a test only has to decide *when* the older page exists
(`_reveal_older_history`, below).

Simulates the "user scrolled near the edge" trigger by emitting
ChartCard.sig_near_left_edge directly rather than a real drag gesture — this
repo has no existing precedent for simulating a pyqtgraph mouse-drag pan
(only QPushButton/QML clicks), and EdgeScrollDetector's own unit tests
already cover the pan-distance math in isolation.

The series comes from `mock_klines.py`, which is where PR 1.1a's cleanup put
it: a copy used to live in this file, and it had already drifted two years
out of date once conftest's moved to the current clock. It is **not**
imported from `conftest.py` — importing a conftest by name runs it a second
time under a second module identity, which aborted this whole tier
mid-run; `mock_klines.py`'s own docstring records that.
"""

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.vo.market_data import MarketData
from Sagittarius_Elite_Warrior.tests.integration.presentation.ui.mock_klines import (
    MOCK_KLINE_COUNT,
    build_mock_klines,
)


def _older_mock_klines(symbol: str) -> list[MarketData]:
    """Newest-first, all strictly older than the oldest candle the screen
    already holds — which is `build_mock_klines()`'s last row, since that
    builder hands its rows back newest-first.

    Derived from that builder rather than from an epoch of its own: the page
    this test prepends has to be *adjacent* to what the chart is showing, and
    PR 1.1a's cleanup found this file's own constant two years away from it
    after conftest moved to the current clock. One source for the anchor, so
    it cannot drift again.
    """
    oldest_shown = build_mock_klines(symbol)[-1].open_time
    klines = []
    for i in range(MOCK_KLINE_COUNT):
        open_time = oldest_shown - timedelta(minutes=MOCK_KLINE_COUNT - i)
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


def _reveal_older_history(seeded_history, symbol: str) -> None:
    """Put an older page in the store, after the first load has already run.

    `EPIC-025` PR 1.1 replaced a hand-rolled dispatcher that returned a
    different batch depending on whether `end_time` was set — its own
    docstring described that as "real handler behavior, just without a real
    database". The port reads a real store, so the timing does the work
    instead: these rows land *after* the screen's initial load, exactly as a
    background sync would have written them, and the load-more read finds
    them because it asks for candles below the boundary it already holds.
    """
    seeded_history.seed(list(reversed(_older_mock_klines(symbol))))


def _open_dashboard(navigate):
    cfg = navigate("dashboard")
    return cfg["presenter_instance"], cfg["view_instance"]


def test_scrolling_near_the_left_edge_prepends_older_candles(
    qtbot, main_window, navigate, seeded_history
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _reveal_older_history(seeded_history, view.chart_cards[0].symbol)
    card = view.chart_cards[0]
    history_before = len(card._raw_history)
    oldest_before = card._raw_history[0][0]

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert len(card._raw_history) == history_before + MOCK_KLINE_COUNT
    assert card._raw_history[0][0] < oldest_before


def test_load_more_does_not_reset_the_current_viewport(
    qtbot, main_window, navigate, seeded_history
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _reveal_older_history(seeded_history, view.chart_cards[0].symbol)
    card = view.chart_cards[0]
    card.plot_layout.main_plot.setXRange(
        card._raw_history[0][0], card._raw_history[-1][0], padding=0
    )
    view_before = card.plot_layout.main_plot.vb.viewRange()

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert card.plot_layout.main_plot.vb.viewRange() == view_before


def test_load_more_rebuilds_scripts_without_dropping_the_active_set(
    qtbot, main_window, navigate, seeded_history
):
    """A prepend forces IndicatorScriptRunner.rebuild() (see
    dashboard_presenter._on_history_prepended's docstring) — the set of
    enabled scripts must come out the other side unchanged."""
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _reveal_older_history(seeded_history, view.chart_cards[0].symbol)
    card = view.chart_cards[0]
    active_before = set(presenter._script_runner.active)

    with qtbot.waitSignal(presenter.ui_history_prepend_finished_signal, timeout=2000):
        card.sig_near_left_edge.emit(card.symbol)

    assert set(presenter._script_runner.active) == active_before


def test_a_second_edge_signal_before_the_first_settles_does_not_double_fetch(
    qtbot, main_window, navigate, seeded_history, monkeypatch
):
    qtbot.addWidget(main_window)
    presenter, view = _open_dashboard(navigate)
    _reveal_older_history(seeded_history, view.chart_cards[0].symbol)
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
