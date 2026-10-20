"""View → Symbol…, Add to Watchlist… and Remove from Watchlist
(`EPIC-033V`): the shared picker over the chosen market's symbols, what a
choice does, and the Watchlist that follows."""

from __future__ import annotations

import pytest
from PySide6.QtCore import QObject
from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import FailureKind
from Sagittarius_Elite_Warrior.src.core.contracts.navigation_source import (
    NavigationSource,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_symbol_catalog import (
    ISymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_symbol_catalog import (
    FakeSymbolCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
    ADD_TO_WATCHLIST,
    CHOOSE_SYMBOL,
    REMOVE_FROM_WATCHLIST,
    market_commands,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_presenter import (
    MarketPresenter,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_screen import (
    MARKET_ROUTE,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.watchlist_stream import (
    WATCHLIST_STREAM_OWNER,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.adapters.in_memory_state_store import (
    InMemoryStateStore,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.symbol_picker import (
    SymbolPickerOverlay,
    SymbolPreferences,
)
from Sagittarius_Elite_Warrior.tests.command_actions import bound_actions

_SPOT = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
_FUTURES = ("BTCUSDT", "XRPUSDT")


class _TwoMarkets(FakeSymbolCatalog):
    """Spot and Futures list different symbols; a read can be made to fail."""

    def __init__(self) -> None:
        super().__init__(_SPOT)
        self.fail = False

    def list_symbols(self, market, *, force_refresh=False):
        if self.fail:
            raise ConnectionError("exchange unreachable")
        if market is MarketType.FUTURES_USD_M:
            self.markets_read.append(market)
            return _FUTURES
        return super().list_symbols(market, force_refresh=force_refresh)


@pytest.fixture
def catalog() -> _TwoMarkets:
    return _TwoMarkets()


@pytest.fixture
def commands(qapp, build, catalog):
    """Builds the presenter on `catalog` and returns it with its commands."""
    owner = QObject()

    def _make(**overrides):
        presenter = build(catalog=catalog, **overrides)
        registry = bound_actions(
            owner, market_commands(MARKET_ROUTE), presenter.bind_commands
        )
        return presenter, registry

    yield _make
    owner.deleteLater()


def _picker(presenter: MarketPresenter) -> SymbolPickerOverlay:
    pickers = presenter.view.findChildren(SymbolPickerOverlay)
    assert len(pickers) == 1
    return pickers[0]


def _choose(presenter: MarketPresenter, symbol: str) -> None:
    picker = _picker(presenter)
    picker.symbol_chosen.emit(symbol)
    picker.close()
    picker.deleteLater()


# -- Symbol… -------------------------------------------------------------------------


def test_symbol_lists_the_chosen_markets_symbols_read_once_off_the_ui_thread(
    commands, catalog, threads
):
    presenter, registry = commands()

    registry.action(CHOOSE_SYMBOL).trigger()
    assert catalog.markets_read == []
    threads.run_all()
    picker = _picker(presenter)
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    assert catalog.markets_read == [MarketType.SPOT]
    assert list(picker._get_symbols()) == list(_SPOT)


def test_choosing_a_symbol_opens_its_chart(commands, threads):
    presenter, registry = commands()
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    _choose(presenter, "SOLUSDT")

    assert "SOLUSDT" in presenter.charts
    assert presenter.view.current_symbol == "SOLUSDT"
    assert presenter.tracked.entries == ("BTCUSDT", "ETHUSDT", "BNBUSDT")


def test_choosing_an_open_symbol_brings_its_chart_forward(commands, threads):
    presenter, registry = commands()
    presenter.on_mode_shown(NavigationSource.RESTORE)
    presenter.view.symbol_opened.emit("ETHUSDT")
    chart = presenter.charts["ETHUSDT"]
    presenter.view.show_chart("BTCUSDT")
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    _choose(presenter, "ETHUSDT")

    assert presenter.charts["ETHUSDT"] is chart
    assert presenter.view.current_symbol == "ETHUSDT"
    assert presenter.view.open_symbols == ("BTCUSDT", "ETHUSDT")


def test_the_picker_marks_the_chart_in_front_as_current(commands, threads):
    presenter, registry = commands()
    presenter.on_mode_shown(NavigationSource.RESTORE)

    registry.action(CHOOSE_SYMBOL).trigger()

    assert _picker(presenter)._get_current() == "BTCUSDT"


def test_the_other_market_lists_its_own_symbols_once(commands, catalog, threads):
    from Sagittarius_Elite_Warrior.src.modules.trading.ui.market.market_commands import (
        SHOW_FUTURES,
    )

    presenter, registry = commands()
    registry.action(SHOW_FUTURES).trigger()

    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()
    picker = _picker(presenter)
    picker.close()
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    assert catalog.markets_read == [MarketType.FUTURES_USD_M]
    assert list(
        presenter.view.findChildren(SymbolPickerOverlay)[-1]._get_symbols()
    ) == (list(_FUTURES))


def test_a_failed_read_is_told_and_the_next_opening_asks_again(
    commands, catalog, threads, notifier
):
    presenter, registry = commands()
    catalog.fail = True

    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    notice = notifier.last
    assert notice.kind is FailureKind.BACKGROUND
    assert notice.scope == MARKET_ROUTE
    assert "Spot" in notice.headline

    catalog.fail = False
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()
    assert list(
        presenter.view.findChildren(SymbolPickerOverlay)[-1]._get_symbols()
    ) == (list(_SPOT))
    assert notifier.cleared


def test_a_chosen_symbol_is_a_recent_one(qapp, build, catalog, threads):
    preferences = SymbolPreferences()
    owner = QObject()
    presenter = build(catalog=catalog, preferences=preferences)
    registry = bound_actions(
        owner, market_commands(MARKET_ROUTE), presenter.bind_commands
    )
    registry.action(CHOOSE_SYMBOL).trigger()
    threads.run_all()

    _choose(presenter, "SOLUSDT")

    assert preferences.recents[0] == "SOLUSDT"
    owner.deleteLater()


# -- Add to Watchlist… -----------------------------------------------------------------


def test_adding_a_symbol_tracks_it_and_keeps_the_prices_of_the_others(
    commands, threads
):
    presenter, registry = commands()
    presenter.view.watchlist.update_tick("ETHUSDT", 3000.0, 1.5, 10.0)
    registry.action(ADD_TO_WATCHLIST).trigger()
    threads.run_all()

    _choose(presenter, "SOLUSDT")

    rows = {row.symbol: row for row in presenter.view.watchlist.rows}
    assert list(rows) == ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
    assert rows["ETHUSDT"].last_price == 3000.0
    assert rows["SOLUSDT"].last_price is None
    assert "SOLUSDT" not in presenter.charts


def test_adding_a_tracked_symbol_adds_no_second_row(commands, threads):
    presenter, registry = commands()
    registry.action(ADD_TO_WATCHLIST).trigger()
    threads.run_all()

    _choose(presenter, "BTCUSDT")

    assert [row.symbol for row in presenter.view.watchlist.rows].count("BTCUSDT") == 1
    assert presenter.tracked.entries == ("BTCUSDT", "ETHUSDT", "BNBUSDT")


def test_adding_while_live_streams_the_new_symbol_too(commands, threads):
    stream = FakeMarketStream()
    presenter, registry = commands(stream=stream)
    presenter.on_mode_shown(NavigationSource.USER_INTENT)
    registry.action(ADD_TO_WATCHLIST).trigger()
    threads.run_all()

    _choose(presenter, "SOLUSDT")

    held = stream.held_by(WATCHLIST_STREAM_OWNER)
    assert held is not None
    assert held.symbols == ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")


def test_adding_before_going_live_streams_nothing(commands, threads):
    stream = FakeMarketStream()
    presenter, registry = commands(stream=stream)
    presenter.on_mode_shown(NavigationSource.RESTORE)
    registry.action(ADD_TO_WATCHLIST).trigger()
    threads.run_all()

    _choose(presenter, "SOLUSDT")

    assert stream.calls == []


def test_the_watchlist_is_remembered_across_a_restart(commands, threads):
    store = InMemoryStateStore()
    coordinator = UiStateCoordinator(store)
    presenter, registry = commands(state=coordinator)
    registry.action(ADD_TO_WATCHLIST).trigger()
    threads.run_all()
    _choose(presenter, "SOLUSDT")
    coordinator.flush()

    again, _registry = commands(state=UiStateCoordinator(store))

    assert again.tracked.entries == ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT")
    assert [row.symbol for row in again.view.watchlist.rows] == list(
        again.tracked.entries
    )


# -- Remove from Watchlist -------------------------------------------------------------


def _select(presenter: MarketPresenter, symbol: str) -> None:
    view = presenter.view._watchlist.view
    for row in range(presenter.view._watchlist.proxy.rowCount()):
        if presenter.view._watchlist.text(row, 0) == symbol:
            view.selectRow(row)
            return
    raise AssertionError(symbol)


def test_remove_is_off_until_a_row_is_selected(commands):
    presenter, registry = commands()
    remove = registry.action(REMOVE_FROM_WATCHLIST)
    assert not remove.isEnabled()

    _select(presenter, "ETHUSDT")
    assert remove.isEnabled()
    assert presenter.view.selected_watchlist_symbol == "ETHUSDT"


def test_remove_untracks_the_selected_symbol_and_keeps_its_chart(commands):
    presenter, registry = commands()
    presenter.view.symbol_opened.emit("ETHUSDT")
    _select(presenter, "ETHUSDT")

    registry.action(REMOVE_FROM_WATCHLIST).trigger()

    assert presenter.tracked.entries == ("BTCUSDT", "BNBUSDT")
    assert [row.symbol for row in presenter.view.watchlist.rows] == [
        "BTCUSDT",
        "BNBUSDT",
    ]
    assert "ETHUSDT" in presenter.charts
    assert not registry.action(REMOVE_FROM_WATCHLIST).isEnabled()


def test_removing_while_live_streams_the_rest_and_the_last_one_stops_it(commands):
    stream = FakeMarketStream()
    presenter, registry = commands(stream=stream, symbols=("BTCUSDT", "ETHUSDT"))
    presenter.on_mode_shown(NavigationSource.USER_INTENT)

    _select(presenter, "ETHUSDT")
    registry.action(REMOVE_FROM_WATCHLIST).trigger()
    held = stream.held_by(WATCHLIST_STREAM_OWNER)
    assert held is not None
    assert held.symbols == ("BTCUSDT",)

    _select(presenter, "BTCUSDT")
    registry.action(REMOVE_FROM_WATCHLIST).trigger()
    assert stream.held_by(WATCHLIST_STREAM_OWNER) is None
    assert presenter.view.stream.text() == "Market data: the Watchlist is empty."


def test_the_commands_are_view_menu_items_with_a_toolbar_button_for_the_two_that_ask():
    by_id = {c.command_id: c for c in market_commands(MARKET_ROUTE)}

    assert by_id[CHOOSE_SYMBOL].shortcut == "Ctrl+L"
    assert by_id[CHOOSE_SYMBOL].on_toolbar and by_id[CHOOSE_SYMBOL].needs_input
    assert by_id[ADD_TO_WATCHLIST].on_toolbar and by_id[ADD_TO_WATCHLIST].needs_input
    assert not by_id[REMOVE_FROM_WATCHLIST].on_toolbar
    assert not by_id[REMOVE_FROM_WATCHLIST].needs_input
    assert {
        c.menu_path
        for c in by_id.values()
        if c.command_id in {CHOOSE_SYMBOL, ADD_TO_WATCHLIST, REMOVE_FROM_WATCHLIST}
    } == {("&View",)}


def test_the_catalog_is_the_ports_type():
    assert issubclass(_TwoMarkets, ISymbolCatalog)
