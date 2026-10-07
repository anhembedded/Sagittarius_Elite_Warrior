"""`EPIC-033I` — the Trade menu as HLD §11.2.3 lists it: Venue › one choice per
venue, New order… (F9) and Emergency stop (F8),
which is on every mode's toolbar and asks first.

What the trading module really contributes (`real_contributions`), and the
contribution function over each set of venues a run can enable.
"""

from __future__ import annotations

from unittest.mock import Mock

from Sagittarius_Elite_Warrior.src.modules.trading.ui.trade.trade_commands import (
    CANCEL_ALL,
    CANCEL_ORDER,
    CLOSE_POSITION,
    EMERGENCY_STOP,
    HIDE_OTHER_PAIRS,
    NEW_ORDER,
    VENUE_CHOICE,
    VENUE_MENU,
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
    assert {NEW_ORDER, EMERGENCY_STOP} <= commands


def test_the_trade_menu_reads_as_the_catalogue_lists_it() -> None:
    commands = trade_commands(TRADE_ROUTE, (FUTURES, SPOT))
    trade_menu = [c.text for c in commands if c.menu_path[0] == "T&rade"]

    assert trade_menu == [
        "&Futures Testnet",
        "&Spot Testnet",
        "&New order…",
        "Cancel &order",
        "Cancel a&ll orders",
        "&Close position",
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


def test_a_venue_the_run_does_not_serve_is_not_listed() -> None:
    only_spot = _by_id((SPOT,))

    assert venue_choice_id(SPOT) in only_spot
    assert venue_choice_id(FUTURES) not in only_spot
    assert not any(c.exclusive_group == VENUE_CHOICE for c in _by_id(()).values())


def test_there_is_no_command_that_turns_trading_on_or_off() -> None:
    """`EPIC-034C` — Start bot, arm a strategy and a manual order open the
    order session; Emergency stop closes it. Nothing else switches it."""
    texts = [
        c.text.replace("&", "").lower()
        for c in trade_commands(TRADE_ROUTE, (FUTURES, SPOT))
    ]

    assert not any("trading" in t and ("enable" in t or "disable" in t) for t in texts)
    assert not any(
        "enable_trading" in c.command_id
        for c in trade_commands(TRADE_ROUTE, (FUTURES,))
    )


def test_new_order_is_the_modes_with_its_shortcut() -> None:
    new_order = _by_id((FUTURES,))[NEW_ORDER]

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


def test_the_table_commands_take_their_keys_and_ask_through_their_tables() -> None:
    """Cancel order is the platform's Delete; Cancel all orders is on the
    toolbar; each asks with its own verbs in its table's dialog, so none
    declares the Engine's confirmation."""
    commands = _by_id((FUTURES,))
    cancel, cancel_all, close = (
        commands[CANCEL_ORDER],
        commands[CANCEL_ALL],
        commands[CLOSE_POSITION],
    )

    assert cancel.standard_shortcut == "Delete"
    assert cancel_all.on_toolbar
    assert not close.on_toolbar
    for command in (cancel, cancel_all, close):
        assert command.mode == TRADE_ROUTE
        assert command.confirm is None
        assert not command.needs_input


def test_all_four_venues_are_menu_entries_with_one_access_key_each() -> None:
    """`EPIC-034` D11 — a second venue per market must not share its twin's key."""
    venues = [v for v in TradingVenue if v.supports_order_submission]
    commands = trade_commands(TRADE_ROUTE, tuple(venues))
    entries = [c.text for c in commands if c.menu_path == VENUE_MENU]
    keys = [text[text.index("&") + 1].lower() for text in entries]

    assert entries == [
        "&Futures Testnet",
        "&Spot Testnet",
        "F&utures Mainnet",
        "S&pot Mainnet",
    ]
    assert len(set(keys)) == len(keys)
