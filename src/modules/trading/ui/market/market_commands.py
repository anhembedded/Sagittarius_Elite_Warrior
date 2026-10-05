"""The Market mode's commands (`EPIC-033H`): Tools → Check connection,
File → Close chart and View → Spot market or Futures market (`EPIC-033Q`).

- **Check connection:** HLD §11.2.3 lists it in Tools, with no shortcut, no
  toolbar and no confirmation. It belongs to every mode (`mode=None`): the
  connection state it refreshes is in the window's status bar, which every
  mode shows. The Market presenter performs it, because the Market mode owns
  SPEC-003 (HLD §11.2.1).
- **Close chart:** closes the chart tab in front, the keyboard's way to what a
  tab's close button does (`ui-presentation-rule.md` §11). It is the
  platform's Close (Ctrl+F4 or Ctrl+W on Windows), in File as Windows puts
  it, scoped to the mode.
- **View → Spot market, Futures market:** which market the Watchlist and
  every chart show, a value of the mode rather than of each chart
  (`EPIC-033Q`). Two checkable commands in one exclusive group: option
  items in View, where Windows puts a choice of what a window shows (MS
  `cmd-menus`), and on the mode's toolbar, so the market in view is visible
  without opening a menu. View rather than a menu of their own: a "Market"
  title needs an access key, and every letter of the word is already a
  menu-bar title's or a Backtest panel's key.
- **View → Load older candles, Load range…:** what the chart in front shows
  beyond its first window (`EPIC-033S`), in View beside the market choice
  for the same reason; Load range… asks a UTC span first, so it ends with
  "…". Off while no chart is open and while the one in front loads.
- **Tools → Indicator parameters…:** edits the parameters of the script
  selected in the Indicators panel, in the dialog the Dev Board used for it
  (`BOT-063`), which the Dev Board's deletion (`EPIC-033P`) would otherwise
  take with it. In Tools, beside Options, as a dialog of settings; off while
  the selected script declares no input.

Qt-free, because `TradingModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

FILE_MENU = ("&File",)
TOOLS_MENU = ("&Tools",)
VIEW_MENU = ("&View",)
CHECK_CONNECTION = "trading.market.check_connection"
CLOSE_CHART = "trading.market.close_chart"
SHOW_SPOT = "trading.market.show_spot"
SHOW_FUTURES = "trading.market.show_futures"
LOAD_OLDER = "trading.market.load_older"
LOAD_RANGE = "trading.market.load_range"
INDICATOR_PARAMS = "trading.market.indicator_params"
#: The `exclusive_group` of Spot and Futures.
MARKET_CHOICE = "trading.market.market"


def market_commands(route: str) -> tuple[CommandContribution, ...]:
    """The commands the Market mode at `route` performs, in menu order."""
    return (
        CommandContribution(
            contributor_id="trading",
            command_id=CLOSE_CHART,
            text="&Close chart",
            menu_path=FILE_MENU,
            mode=route,
            standard_shortcut="Close",
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=SHOW_SPOT,
            text="S&pot market",
            menu_path=VIEW_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
            exclusive_group=MARKET_CHOICE,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=SHOW_FUTURES,
            text="Futures mar&ket",
            menu_path=VIEW_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
            exclusive_group=MARKET_CHOICE,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=LOAD_OLDER,
            text="Load o&lder candles",
            menu_path=VIEW_MENU,
            mode=route,
            on_toolbar=True,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=LOAD_RANGE,
            text="Load ran&ge…",
            menu_path=VIEW_MENU,
            mode=route,
            on_toolbar=True,
            needs_input=True,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=INDICATOR_PARAMS,
            text="&Indicator parameters…",
            menu_path=TOOLS_MENU,
            mode=route,
            needs_input=True,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=CHECK_CONNECTION,
            text="Check &connection",
            menu_path=TOOLS_MENU,
            mode=None,
            on_toolbar=False,
        ),
    )
