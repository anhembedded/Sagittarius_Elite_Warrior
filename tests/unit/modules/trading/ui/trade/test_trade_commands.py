"""`EPIC-033I` — the Trade menu as HLD §11.2.3 lists it: Venue › one choice per
enabled venue, Enable live trading, New order… (F9) and Emergency stop (F8),
which is on every mode's toolbar and asks first.

What the trading module really contributes (`real_contributions`), and the
contribution function over each set of venues a run can enable.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    EMERGENCY_STOP,
    ENABLE_TRADING,
    HIDE_OTHER_PAIRS,
    NEW_ORDER,
    VENUE_CHOICE,
    emergency_stop_consequence,
    trade_commands,
    venue_choice_id,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_screen import (
    TRADE_ROUTE,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.conftest import real_contributions

FUTURES = TradingVenue.FUTURES_TESTNET
SPOT = TradingVenue.SPOT_TESTNET


def _by_id(venues: tuple[TradingVenue, ...]) -> dict:
    return {c.command_id: c for c in trade_commands(TRADE_ROUTE, venues)}


def test_the_trading_module_contributes_one_trade_mode_and_no_desks() -> None:
    contributions = real_contributions(Mock())
    routes = {screen.route for screen in contributions.screens()}
    commands = {command.command_id for command in contributions.commands()}

    assert TRADE_ROUTE in routes
    assert not {"trading.futures", "trading.spot"} & routes
    assert {ENABLE_TRADING, NEW_ORDER, EMERGENCY_STOP} <= commands


def test_the_trade_menu_reads_as_the_catalogue_lists_it() -> None:
    commands = trade_commands(TRADE_ROUTE, (FUTURES, SPOT))
    trade_menu = [c.text for c in commands if c.menu_path[0] == "T&rade"]

    assert trade_menu == [
        "&Futures",
        "&Spot",
        "&Enable live trading",
        "&New order…",
        "Emergency &stop",
    ]


def test_each_enabled_venue_is_one_exclusive_choice_on_the_toolbar() -> None:
    commands = _by_id((FUTURES, SPOT))

    for venue in (FUTURES, SPOT):
        choice = commands[venue_choice_id(venue)]
        assert choice.menu_path == ("T&rade", "&Venue")
        assert choice.mode == TRADE_ROUTE
        assert choice.checkable
        assert choice.on_toolbar
        assert choice.exclusive_group == VENUE_CHOICE


def test_a_venue_that_is_not_enabled_is_not_listed() -> None:
    only_spot = _by_id((SPOT,))

    assert venue_choice_id(SPOT) in only_spot
    assert venue_choice_id(FUTURES) not in only_spot
    assert not any(c.exclusive_group == VENUE_CHOICE for c in _by_id(()).values())


def test_enable_and_new_order_are_the_modes_with_their_shortcuts() -> None:
    commands = _by_id((FUTURES,))
    enable, new_order = commands[ENABLE_TRADING], commands[NEW_ORDER]

    assert (enable.mode, enable.checkable, enable.on_toolbar) == (
        TRADE_ROUTE,
        True,
        True,
    )
    assert enable.confirm is None
    assert (new_order.mode, new_order.shortcut, new_order.needs_input) == (
        TRADE_ROUTE,
        "F9",
        True,
    )
    assert new_order.on_toolbar


def test_emergency_stop_is_on_every_modes_toolbar_and_asks_with_its_own_verb() -> None:
    stop = _by_id((FUTURES, SPOT))[EMERGENCY_STOP]

    assert stop.mode is None
    assert stop.on_toolbar
    assert stop.shortcut == "F8"
    assert stop.menu_path == ("T&rade",)
    assert stop.confirm is not None
    assert stop.confirm.title == "Emergency Stop"
    assert stop.confirm.accept_text == "Stop everything"


def test_emergency_stop_names_every_venue_and_what_it_closes_on_each() -> None:
    both = emergency_stop_consequence((FUTURES, SPOT))

    assert "Futures Testnet and Spot Testnet" in both
    assert "every open order is cancelled" in both
    assert "every Futures position is closed at market" in both
    assert "sold at market" in both
    assert "Futures" not in emergency_stop_consequence((SPOT,))


def test_hide_other_pairs_is_a_checkable_view_command_of_the_mode() -> None:
    hide = _by_id((FUTURES,))[HIDE_OTHER_PAIRS]

    assert hide.menu_path == ("&View",)
    assert (hide.mode, hide.checkable, hide.on_toolbar) == (TRADE_ROUTE, True, False)
