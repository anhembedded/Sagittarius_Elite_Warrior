"""The Trade mode's commands (`EPIC-033I`, HLD §11.2.3's Trade menu).

- **Trade → Venue › Futures, Spot:** which venue the mode trades. One
  checkable command per venue the app assembles (every one that can place
  orders, `EPIC-034B`), in one exclusive group, also on the mode's toolbar, so
  the venue in use is visible without opening a menu (MS `cmd-menus`, option
  items). A venue with no key is listed too; its connection check names the missing key.
- **Enable live trading:** checkable, on the toolbar, for the chosen venue.
  Turning it on asks first (HLD §11.2.3: "on enable"); turning it off does
  not. The Engine's action would ask on every trigger, so the mode asks
  itself (`TradeCommandBinding`, `TradeView.ask_to_enable`).
- **New order… (F9):** moves the keyboard focus to the chosen venue's order
  entry and places nothing; the order is placed by the entry's own button,
  which asks first (`order_confirmation.py`). It ends with "…" because the
  order needs input before it is sent.
- **View → Hide other pairs:** the chosen venue's account tables show its
  symbol only (`EPIC-033I` stage 2; a check box beside the tabs before the
  tables became panels). Checkable; it follows the chosen venue.
- **Cancel order (Del), Cancel all orders, Close position** (`EPIC-033I`
  stage 3): the chosen venue's account tables' own actions, which ask
  first with their verbs and act on what the table selects or shows; Cancel
  all orders is also on the toolbar (HLD §11.2.3). Close position is not in
  the catalogue's table, which predates the tables leaving their toolbars;
  it is the Positions table's action, off on Spot. None ends with "…": each
  only confirms.
- **Emergency stop (F8):** in the Trade menu and on every mode's toolbar
  (`mode=None`), HLD §11.2.2: the one command that must never be a menu
  away. It stops every enabled venue, not only the one chosen: from another
  mode no venue shows, and the person pressing it wants trading stopped. It
  asks first, naming what it does on each market; the answer is "Stop
  everything", Cancel the default (`ui-presentation-rule.md` §10).

Which venues exist is the module's, fixed at boot (`TradingModule.boot`); this file is Qt-free, because
`TradingModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`).

Plausible extensions, each a local change: a third venue (a profile in
`desk_profile.py`, nothing here); a table action the menu should drive
(one command here and one key in `AccountTabsPanel.menu_actions()`).
"""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandConfirmation,
    CommandContribution,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_profile import (
    desk_profile_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.charting.chart_commands import (
    chart_commands,
)

TRADE_MENU = ("T&rade",)
VENUE_MENU = ("T&rade", "&Venue")
CHART_MENU = ("&View", "C&hart")
#: The prefix of the chart's commands' ids (`chart_command_id`).
CHART_PREFIX = "trading.trade"
ENABLE_TRADING = "trading.trade.enable_trading"
HIDE_OTHER_PAIRS = "trading.trade.hide_other_pairs"
VIEW_MENU = ("&View",)
NEW_ORDER = "trading.trade.new_order"
CANCEL_ORDER = "trading.trade.cancel_order"
CANCEL_ALL = "trading.trade.cancel_all"
CLOSE_POSITION = "trading.trade.close_position"
EMERGENCY_STOP = "trading.emergency_stop"
#: The `exclusive_group` of the venue choices.
VENUE_CHOICE = "trading.trade.venue"
_CONTRIBUTOR = "trading"

#: What Emergency stop does after turning trading off, per market
#: (`EmergencyStopCommandHandler`, step 3).
_WHAT_IT_CLOSES = {
    MarketType.FUTURES_USD_M: "every Futures position is closed at market",
    MarketType.SPOT: "what was bought on Spot since trading was enabled is sold at market",
}


def venue_choice_id(venue: TradingVenue) -> str:
    return f"{VENUE_CHOICE}.{venue.value}"


def trade_commands(
    route: str, venues: Sequence[TradingVenue]
) -> tuple[CommandContribution, ...]:
    """The commands of the Trade mode at `route`, which trades `venues` (the
    ones enabled in this run), in menu order."""
    return (
        *(_venue_choice(route, venue) for venue in venues),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=ENABLE_TRADING,
            text="&Enable live trading",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=NEW_ORDER,
            text="&New order…",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
            shortcut="F9",
            needs_input=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=CANCEL_ORDER,
            text="Cancel &order",
            menu_path=TRADE_MENU,
            mode=route,
            standard_shortcut="Delete",
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=CANCEL_ALL,
            text="Cancel a&ll orders",
            menu_path=TRADE_MENU,
            mode=route,
            on_toolbar=True,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=CLOSE_POSITION,
            text="&Close position",
            menu_path=TRADE_MENU,
            mode=route,
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=EMERGENCY_STOP,
            text="Emergency &stop",
            menu_path=TRADE_MENU,
            mode=None,
            on_toolbar=True,
            shortcut="F8",
            confirm=CommandConfirmation(
                title="Emergency Stop",
                consequence=emergency_stop_consequence(venues),
                accept_text="Stop everything",
            ),
        ),
        CommandContribution(
            contributor_id=_CONTRIBUTOR,
            command_id=HIDE_OTHER_PAIRS,
            text="Hide other pair&s",
            menu_path=VIEW_MENU,
            mode=route,
            checkable=True,
        ),
        *chart_commands(_CONTRIBUTOR, CHART_PREFIX, route, CHART_MENU),
    )


def emergency_stop_consequence(venues: Sequence[TradingVenue]) -> str:
    """What Emergency stop says it will do, venue by venue."""
    profiles = [desk_profile_for(venue) for venue in venues]
    names = " and ".join(f"{profile.title} Testnet" for profile in profiles)
    clauses = [
        "every open order is cancelled",
        *(_WHAT_IT_CLOSES[profile.market_type] for profile in profiles),
    ]
    listed = (
        ", ".join(clauses[:-1]) + f" and {clauses[-1]}"
        if len(clauses) > 1
        else clauses[0]
    )
    return f"Live trading turns off on {names or 'every enabled venue'}; {listed}."


def _venue_choice(route: str, venue: TradingVenue) -> CommandContribution:
    return CommandContribution(
        contributor_id=_CONTRIBUTOR,
        command_id=venue_choice_id(venue),
        text=f"&{desk_profile_for(venue).title}",
        menu_path=VENUE_MENU,
        mode=route,
        on_toolbar=True,
        checkable=True,
        exclusive_group=VENUE_CHOICE,
    )
