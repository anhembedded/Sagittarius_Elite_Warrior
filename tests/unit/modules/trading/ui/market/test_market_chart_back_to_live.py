"""View → Back to live (`EPIC-033T`): a Market chart showing a range draws its
newest first window again and follows the stream, in one request; the
command is off while the chart in front shows no range and while it loads."""

from __future__ import annotations

from datetime import timedelta

import pytest
from PySide6.QtCore import QCoreApplication, QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.chart_history import (
    HistoryRange,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    BACK_TO_LIVE,
    LOAD_RANGE,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    START,
    candle,
    tick,
)

_MINUTE = timedelta(minutes=1)
_RANGE = HistoryRange(START - 50 * _MINUTE, START - 41 * _MINUTE)


@pytest.fixture
def actions(qapp):
    owner = QObject()

    def _bind(presenter: MarketPresenter):
        registry = bound_actions(
            owner, market_commands(MARKET_ROUTE), presenter.bind_commands
        )
        return registry.action(LOAD_RANGE), registry.action(BACK_TO_LIVE)

    yield _bind
    owner.deleteLater()


@pytest.fixture
def ranged(build, threads, history, actions, monkeypatch):
    """BTCUSDT live, its first window drawn (minutes 0–59), then the range
    of minutes -50 to -41 drawn in its place."""
    history.seed([candle("BTCUSDT", minute) for minute in range(-100, 60)])
    presenter = build()
    load_range, back_to_live = actions(presenter)
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    threads.run_all()
    monkeypatch.setattr(
        presenter.view, "ask_history_range", lambda _symbol, _proposed: _RANGE
    )
    load_range.trigger()
    threads.run_all()
    return presenter, back_to_live


def _opens(chart) -> list[int]:
    return [int((k.open_time - START) / _MINUTE) for k in chart._klines]


def test_back_to_live_draws_the_newest_window_and_takes_live_candles_again(
    ranged, threads, event_bus
):
    presenter, back_to_live = ranged
    chart = presenter.charts["BTCUSDT"]
    assert chart.showing_range
    assert back_to_live.isEnabled()

    back_to_live.trigger()
    threads.run_all()
    event_bus.emit(tick(candle("BTCUSDT", 60)))
    QCoreApplication.processEvents()

    assert not chart.showing_range
    assert _opens(chart) == list(range(61))


def test_back_to_live_restarts_the_stream_once(ranged, threads, feed):
    """One request: the chart's own stream is asked for again exactly once,
    at the timeframe it shows, not through a detour by another one."""
    _presenter, back_to_live = ranged
    starts = feed.started.count("market.BTCUSDT")

    back_to_live.trigger()
    threads.run_all()

    assert feed.started.count("market.BTCUSDT") == starts + 1


def test_back_to_live_is_off_while_the_chart_in_front_shows_no_range(
    build, threads, actions
):
    presenter = build()
    _load_range, back_to_live = actions(presenter)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()

    assert presenter.charts
    assert not back_to_live.isEnabled()


def test_back_to_live_is_off_while_its_window_loads_and_after_it_draws(ranged, threads):
    presenter, back_to_live = ranged
    chart = presenter.charts["BTCUSDT"]

    back_to_live.trigger()
    assert chart.loading
    assert not back_to_live.isEnabled()

    threads.run_all()
    assert not back_to_live.isEnabled()


def test_back_to_live_is_off_while_no_chart_is_open(ranged):
    presenter, back_to_live = ranged

    presenter.view.chart_closed.emit("BTCUSDT")

    assert not back_to_live.isEnabled()
