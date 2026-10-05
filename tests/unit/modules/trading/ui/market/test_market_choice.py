"""Market → Spot or Futures (`EPIC-033Q`): one exclusive choice of the mode,
Spot by default and remembered; the Watchlist and every chart show the
chosen market, and nothing of the other reaches them."""

from __future__ import annotations

from unittest.mock import Mock

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    MARKET_MENU,
    SHOW_FUTURES,
    SHOW_SPOT,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    WATCHLIST_STREAM_OWNER,
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.state_scope import StateScope
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions
from Sagittarius_Elite_Warrior.tests.unit.modules.trading.ui.market.market_fixtures import (
    candle,
    tick,
)
from sagittarius_engine.extensions.pyside_mvc.workbench import shell_menus
from sagittarius_engine.extensions.pyside_mvc.workbench.action_text import (
    access_keys,
)

_FUTURES = MarketType.FUTURES_USD_M


@pytest.fixture
def actions(qapp):
    """The presenter's Market commands as the window builds them."""
    owner = QObject()

    def _bind(presenter: MarketPresenter):
        registry = bound_actions(
            owner, market_commands(MARKET_ROUTE), presenter.bind_commands
        )
        return registry.action(SHOW_SPOT), registry.action(SHOW_FUTURES)

    yield _bind
    owner.deleteLater()


def _settle() -> None:
    QCoreApplication.processEvents()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


# -- the choice -------------------------------------------------------------------


def test_spot_is_checked_until_the_person_chooses(build, actions):
    presenter = build()

    spot, futures = actions(presenter)

    assert presenter.choice.current is MarketType.SPOT
    assert (spot.isChecked(), futures.isChecked()) == (True, False)
    assert spot.actionGroup() is futures.actionGroup() is not None


def test_the_two_markets_are_one_exclusive_choice(build, actions):
    presenter = build()
    spot, futures = actions(presenter)

    futures.trigger()
    assert (spot.isChecked(), futures.isChecked()) == (False, True)
    assert presenter.choice.current is _FUTURES

    futures.trigger()
    assert (spot.isChecked(), futures.isChecked()) == (False, True)
    assert presenter.choice.current is _FUTURES

    spot.trigger()
    assert (spot.isChecked(), futures.isChecked()) == (True, False)
    assert presenter.choice.current is MarketType.SPOT


def test_choosing_the_market_in_view_again_reopens_nothing(build, actions, threads):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    spot, _futures = actions(presenter)
    chart = presenter.charts["BTCUSDT"]

    spot.trigger()

    assert presenter.charts["BTCUSDT"] is chart
    assert spot.isChecked()


def test_the_chosen_market_is_remembered_for_the_next_run(build, actions):
    coordinator = UiStateCoordinator(InMemoryStateStore())
    first = build(state=coordinator)
    _spot, futures = actions(first)

    futures.trigger()
    coordinator.flush()
    second = build(state=coordinator)
    spot, futures = actions(second)

    assert second.choice.current is _FUTURES
    assert (spot.isChecked(), futures.isChecked()) == (False, True)


def test_a_remembered_market_the_mode_does_not_offer_keeps_spot(build):
    store = InMemoryStateStore()
    store.write(StateScope(key="market"), {"market": "futures_coin_m"})

    presenter = build(state=UiStateCoordinator(store))

    assert presenter.choice.current is MarketType.SPOT


def test_the_menu_and_its_choices_take_no_access_key_of_the_menu_bar():
    """Alt+K opens the Market menu (M is the Backtest run setup's
    `&Market:`); Spot and Futures take no key a menu-bar
    title already holds (the review of PR #355 found three that did)."""
    standard = [
        shell_menus.FILE_MENU,
        shell_menus.EDIT_MENU,
        shell_menus.VIEW_MENU,
        shell_menus.TOOLS_MENU,
        shell_menus.WINDOW_MENU,
        shell_menus.HELP_MENU,
    ]
    titles = set(standard) | {
        c.menu_path[0] for c in real_contributions(Mock()).commands()
    }
    others = {key for title in titles - {MARKET_MENU[0]} for key in access_keys(title)}
    choices = [c for c in market_commands(MARKET_ROUTE) if c.menu_path == MARKET_MENU]
    keys = [key for c in choices for key in access_keys(c.text)]

    assert MARKET_MENU[0] in titles
    (menu_key,) = access_keys(MARKET_MENU[0])
    assert menu_key not in others
    assert sorted(set(keys) & (others | {menu_key})) == []
    assert len(keys) == len(set(keys)) == 2


# -- what the mode shows ----------------------------------------------------------


def test_switching_reopens_every_chart_on_the_new_markets_candles(
    build, actions, threads, feed, futures_feed
):
    presenter = build()
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    presenter.view.symbol_opened.emit("ETHUSDT")
    presenter.view.show_chart("BTCUSDT")
    threads.run_all()
    _spot, futures = actions(presenter)
    feed.stopped.clear()

    futures.trigger()
    threads.run_all()
    _settle()

    assert presenter.view.open_symbols == ("BTCUSDT", "ETHUSDT")
    assert presenter.view.current_symbol == "BTCUSDT"
    assert set(feed.stopped) == {"market.BTCUSDT", "market.ETHUSDT"}
    assert futures_feed.started == ["market.BTCUSDT", "market.ETHUSDT"]


def test_switching_while_live_moves_the_watchlist_stream(build, actions):
    stream = FakeMarketStream()
    presenter = build(stream=stream)
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    _spot, futures = actions(presenter)

    futures.trigger()

    held = stream.held_by(WATCHLIST_STREAM_OWNER)
    assert held is not None
    assert held.market_type is _FUTURES


def test_switching_before_going_live_streams_nothing(build, actions, futures_feed):
    """`BUG-104`: a restored mode stays quiet, whichever market it shows."""
    stream = FakeMarketStream()
    presenter = build(stream=stream)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    _spot, futures = actions(presenter)

    futures.trigger()

    assert stream.calls == []
    assert futures_feed.started == []


def test_switching_leaves_no_price_of_the_previous_market(build, actions, event_bus):
    presenter = build()
    event_bus.emit(tick(candle("ETHUSDT", 0, open_price=100.0)))
    QCoreApplication.processEvents()
    _spot, futures = actions(presenter)

    futures.trigger()

    assert all(row.last_price is None for row in presenter.view.watchlist.rows)


def test_a_tick_of_the_other_market_reaches_neither_the_watchlist_nor_a_chart(
    build, actions, threads
):
    """A tick the Feed let through before the switch arrives after it, on
    the Qt thread's queue: the presenter drops it (`EPIC-033Q`)."""
    presenter = build()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    threads.run_all()
    _spot, futures = actions(presenter)
    futures.trigger()
    threads.run_all()
    _settle()
    drawn = list(presenter.charts["BTCUSDT"]._klines)

    presenter._ticks.marketTick.emit(tick(candle("BTCUSDT", 60)))
    presenter._ticks.marketTick.emit(tick(candle("ETHUSDT", 0)))

    assert presenter.charts["BTCUSDT"]._klines == drawn
    assert all(row.last_price is None for row in presenter.view.watchlist.rows)


def test_a_tick_of_the_chosen_market_still_reaches_its_row(build, actions, event_bus):
    presenter = build()
    _spot, futures = actions(presenter)
    futures.trigger()

    event_bus.emit(tick(candle("ETHUSDT", 0, open_price=100.0), _FUTURES))
    event_bus.emit(tick(candle("BNBUSDT", 0, open_price=100.0)))
    QCoreApplication.processEvents()

    rows = {row.symbol: row for row in presenter.view.watchlist.rows}
    assert rows["ETHUSDT"].percent_change == pytest.approx(1.0)
    assert rows["BNBUSDT"].last_price is None
