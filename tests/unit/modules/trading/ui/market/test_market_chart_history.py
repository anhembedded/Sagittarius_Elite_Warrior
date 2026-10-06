"""View → Load older candles and View → Load range… (`EPIC-033S`) on the
Market chart in front: what they draw, when they are off, and the loads a
closed tab or a new timeframe drops (`async-ui-action-rule.md` §1)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.chart_history import (
    HistoryRange,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    LOAD_OLDER,
    LOAD_RANGE,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.value_formatter import write_value
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    START,
    candle,
    tick,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import ColumnKind

_MINUTE = timedelta(minutes=1)


@pytest.fixture
def actions(qapp):
    owner = QObject()

    def _bind(presenter: MarketPresenter):
        registry = bound_actions(
            owner, market_commands(MARKET_ROUTE), presenter.bind_commands
        )
        return registry.action(LOAD_OLDER), registry.action(LOAD_RANGE)

    yield _bind
    owner.deleteLater()


@pytest.fixture
def opened(build, threads, history, actions):
    """The Market mode with BTCUSDT's first window drawn (minutes 0–59, the
    feed's) and 100 older candles stored before it (minutes -100 to -1)."""
    history.seed([candle("BTCUSDT", minute) for minute in range(-100, 60)])
    presenter = build()
    load_older, load_range = actions(presenter)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    return presenter, load_older, load_range


def _opens(chart) -> list[int]:
    return [int((k.open_time - START) / _MINUTE) for k in chart._klines]


def _logged(presenter: MarketPresenter, text: str) -> bool:
    return any(text in entry.message for entry in presenter.view.log.entries)


# -- Load older candles ---------------------------------------------------------


def test_older_candles_join_the_drawn_ones_with_no_gap_and_no_duplicate(
    opened, threads
):
    presenter, load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]

    load_older.trigger()
    threads.run_all()

    assert _opens(chart) == list(range(-100, 60))
    drawn = [t for t, *_ohlc in chart.chart._raw_history]
    assert drawn == sorted(set(drawn))
    assert len(drawn) == 160


def test_both_commands_are_off_while_the_chart_in_front_loads(opened, threads):
    _presenter, load_older, load_range = opened
    assert load_older.isEnabled()

    load_older.trigger()
    assert not load_older.isEnabled()
    assert not load_range.isEnabled()

    threads.run_all()
    assert load_older.isEnabled()
    assert load_range.isEnabled()


def test_both_commands_are_off_while_no_chart_is_open(opened):
    presenter, load_older, load_range = opened

    presenter.view.chart_closed.emit("BTCUSDT")

    assert not load_older.isEnabled()
    assert not load_range.isEnabled()


def test_a_closed_tab_drops_its_load(opened, threads):
    presenter, load_older, _load_range = opened

    load_older.trigger()
    presenter.view.chart_closed.emit("BTCUSDT")
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    threads.run_all()

    assert not _logged(presenter, "older candles of BTCUSDT")


def test_a_new_timeframe_drops_a_load_asked_against_the_old_one(opened, threads):
    """The 1m window asked for comes back after the chart switched to 1h:
    1m candles prepended to an hourly chart would draw wrong bars."""
    presenter, load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]

    load_older.trigger()
    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    threads.run_all()

    assert -1 not in _opens(chart)
    assert not _logged(presenter, "Loaded 100 older candles")
    assert load_older.isEnabled()


def test_a_new_first_window_drops_a_load_asked_against_the_old_one(opened, threads):
    """Going live redraws the first window at the same timeframe; an older
    window asked before it must not be prepended to the new one."""
    presenter, load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]

    load_older.trigger()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_last()
    threads.run_all()

    assert _opens(chart) == list(range(60))
    assert not _logged(presenter, "Loaded 100 older candles")


def test_the_commands_wait_for_a_first_window_that_never_draws(opened, threads, feed):
    """A stale result lands before the new timeframe's window; nothing is
    stored at 1h, so that window settles without drawing. The commands stay
    off until it settles, then come back."""
    presenter, load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]
    feed.empty.add("1h")

    load_older.trigger()
    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    threads.run_first()
    assert chart.loading
    assert not load_older.isEnabled()

    threads.run_all()
    assert not chart.loading
    assert load_older.isEnabled()


def test_the_commands_are_off_while_a_first_window_loads(opened, threads):
    """Going live asks for a new first window; a range or an older window
    asked meanwhile would be drawn against the window it replaces (the
    review of PR #366)."""
    presenter, load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]

    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    assert chart.loading
    assert not load_older.isEnabled()
    assert not load_range.isEnabled()

    threads.run_all()
    assert load_older.isEnabled()
    assert load_range.isEnabled()


def test_a_range_asked_before_a_new_first_window_is_dropped(
    opened, threads, monkeypatch
):
    """Review of PR #366, probe 1, the order that can still happen: the
    range is asked, then the timeframe changes; the range's read answers
    first. It is not drawn, and the new window is."""
    presenter, _load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]
    _choose(presenter, monkeypatch, HistoryRange(START - 50 * _MINUTE, START))

    load_range.trigger()
    chart.chart.toolbar.sig_timeframe_changed.emit("5m")
    threads.run_first()
    assert not chart.showing_range

    threads.run_all()
    assert not chart.showing_range
    assert {k.interval for k in chart._klines} == {"5m"}


def test_an_older_window_never_mixes_timeframes(opened, threads, history):
    """Review of PR #366, probe 2: 1m candles asked for, then 1h picked; the
    1m read answers before the 1h window. Whatever the order, every drawn
    candle has one timeframe."""
    presenter, load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]

    load_older.trigger()
    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    threads.run_first()
    assert {k.interval for k in chart._klines} == {"1m"}

    threads.run_all()
    assert {k.interval for k in chart._klines} == {"1h"}


def test_an_older_window_answering_before_going_live_is_dropped(opened, threads):
    """Going live asks for a new first window at the same timeframe; the
    older read asked before it answers first, while the window is still in
    flight. It is dropped, not prepended to the window about to go."""
    presenter, load_older, _load_range = opened

    load_older.trigger()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_first()

    assert not _logged(presenter, "Loaded 100 older candles")
    assert presenter.charts["BTCUSDT"].loading


def test_a_window_of_a_timeframe_left_behind_is_not_drawn(opened, threads):
    """1h picked, then 1m again before the 1h window lands: the 1h window
    answering last must not replace the 1m one (`LiveCandleChart` draws only
    the timeframe it shows; the review of PR #366)."""
    presenter, _load_older, _load_range = opened
    chart = presenter.charts["BTCUSDT"]

    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    chart.chart.toolbar.sig_timeframe_changed.emit("1m")
    threads.run_last()
    threads.run_all()

    assert {k.interval for k in chart._klines} == {"1m"}
    assert not chart.loading


def test_nothing_older_is_stored_says_so(build, threads, actions):
    presenter = build()
    load_older, _load_range = actions(presenter)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()

    load_older.trigger()
    threads.run_all()

    assert _logged(presenter, "No older candles of BTCUSDT are stored.")
    assert _opens(presenter.charts["BTCUSDT"]) == list(range(60))


# -- Load range… ------------------------------------------------------------------


def _choose(presenter: MarketPresenter, monkeypatch, span: HistoryRange | None):
    asked: list[HistoryRange] = []

    def ask(symbol: str, proposed: HistoryRange) -> HistoryRange | None:
        asked.append(proposed)
        return span

    monkeypatch.setattr(presenter.view, "ask_history_range", ask)
    return asked


def test_a_range_draws_exactly_its_candles(opened, threads, monkeypatch):
    presenter, _load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]
    asked = _choose(
        presenter, monkeypatch, HistoryRange(START - 50 * _MINUTE, START - 41 * _MINUTE)
    )

    load_range.trigger()
    threads.run_all()

    assert _opens(chart) == list(range(-50, -40))
    assert len(chart.chart._raw_history) == 10
    assert chart.showing_range
    assert asked[0] == HistoryRange(START, START + 60 * _MINUTE)


def _shown(instant) -> str:
    return write_value(ColumnKind.TIMESTAMP, instant)


def test_a_range_says_what_it_shows_in_the_formatters_text(
    opened, threads, monkeypatch
):
    presenter, _load_older, load_range = opened
    span = HistoryRange(START - 50 * _MINUTE, START - 41 * _MINUTE)
    _choose(presenter, monkeypatch, span)

    load_range.trigger()
    threads.run_all()

    assert _logged(
        presenter,
        f"Showing 10 candles of BTCUSDT from {_shown(span.start)} "
        f"to {_shown(span.end)} UTC.",
    )


def test_an_empty_range_says_which_span_holds_nothing(opened, threads, monkeypatch):
    presenter, _load_older, load_range = opened
    span = HistoryRange(START - 900 * _MINUTE, START - 800 * _MINUTE)
    _choose(presenter, monkeypatch, span)

    load_range.trigger()
    threads.run_all()

    assert _logged(
        presenter,
        f"No candles of BTCUSDT are stored from {_shown(span.start)} "
        f"to {_shown(span.end)} UTC.",
    )


def test_a_drawn_range_takes_no_live_candle(opened, threads, monkeypatch, event_bus):
    presenter, _load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]
    _choose(presenter, monkeypatch, HistoryRange(START - 50 * _MINUTE, START))
    load_range.trigger()
    threads.run_all()
    drawn = list(chart._klines)

    event_bus.emit(tick(candle("BTCUSDT", 60)))
    QCoreApplication.processEvents()

    assert chart._klines == drawn


def test_a_new_timeframe_leaves_the_range_and_follows_live_again(
    opened, threads, monkeypatch
):
    presenter, _load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]
    _choose(presenter, monkeypatch, HistoryRange(START - 50 * _MINUTE, START))
    load_range.trigger()
    threads.run_all()

    chart.chart.toolbar.sig_timeframe_changed.emit("1h")
    threads.run_all()

    assert not chart.showing_range


def test_cancel_loads_nothing(opened, threads, monkeypatch):
    presenter, _load_older, load_range = opened
    chart = presenter.charts["BTCUSDT"]
    _choose(presenter, monkeypatch, None)

    load_range.trigger()
    threads.run_all()

    assert _opens(chart) == list(range(60))
    assert not chart.showing_range


def test_a_range_of_the_other_market_reads_the_futures_store(
    build, threads, history, actions, monkeypatch
):
    """`EPIC-033Q` and `EPIC-033S` together: a Futures chart's range is read
    from the Futures shard."""
    history.seed(
        [candle("BTCUSDT", minute, open_price=200.0) for minute in range(-10, 0)],
        MarketType.FUTURES_USD_M,
    )
    presenter = build()
    _load_older, load_range = actions(presenter)
    presenter.choice._on_chosen(MarketType.FUTURES_USD_M)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    _choose(presenter, monkeypatch, HistoryRange(START - 10 * _MINUTE, START))

    load_range.trigger()
    threads.run_all()

    assert _opens(presenter.charts["BTCUSDT"]) == list(range(-10, 0))
    assert history.reads[-1].market is MarketType.FUTURES_USD_M
