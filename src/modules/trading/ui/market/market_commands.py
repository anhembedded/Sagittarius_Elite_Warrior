"""The Market mode's commands (`EPIC-033H`): Tools → Check connection,
File → Close chart and Market → Spot or Futures (`EPIC-033Q`).

- **Check connection:** HLD §11.2.3 lists it in Tools, with no shortcut, no
  toolbar and no confirmation. It belongs to every mode (`mode=None`): the
  connection state it refreshes is in the window's status bar, which every
  mode shows. The Market presenter performs it, because the Market mode owns
  SPEC-003 (HLD §11.2.1).
- **Close chart:** closes the chart tab in front, the keyboard's way to what a
  tab's close button does (`ui-presentation-rule.md` §11). It is the
  platform's Close (Ctrl+F4 or Ctrl+W on Windows), in File as Windows puts
  it, scoped to the mode.

Qt-free, because `TradingModule.contribute()` imports it on a headless run
(`test_module_contribution_laziness.py`).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.command_contribution import (
    CommandContribution,
)

FILE_MENU = ("&File",)
TOOLS_MENU = ("&Tools",)
MARKET_MENU = ("&Market",)
CHECK_CONNECTION = "trading.market.check_connection"
CLOSE_CHART = "trading.market.close_chart"
SHOW_SPOT = "trading.market.show_spot"
SHOW_FUTURES = "trading.market.show_futures"
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
            text="&Spot",
            menu_path=MARKET_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
            exclusive_group=MARKET_CHOICE,
        ),
        CommandContribution(
            contributor_id="trading",
            command_id=SHOW_FUTURES,
            text="F&utures",
            menu_path=MARKET_MENU,
            mode=route,
            on_toolbar=True,
            checkable=True,
            exclusive_group=MARKET_CHOICE,
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
