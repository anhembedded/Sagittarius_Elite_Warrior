"""`EPIC-047E` — what the VPS Bots tab changes in the Bots screen: its doors, and three things it turns off.

@details The tab is the Bots tab's own classes on another backend (charter O4, AC7), so this file holds only the difference:
  · the dispatcher, the candle feeds and the real-money question come from the link (`IVpsTab`), and the question is a typed
    venue every time (`TypedVenueConsent`);
  · the Backtest workbench is not offered: it syncs and replays candles from Binance, which this tab never reads (decision
    record 2026-10-27, D6), and says so where its page would be;
  · New bot is disabled with its reason: its symbol list is the exchange's, and a bot is created in the Bots tab and sent with
    Add to VPS (`EPIC-047E` PR 3);
  · the line above the tab: host, keys, connected or not, the facts' age (charter O5).
Its strategy commands are the Bots tab's own, over the venues of the container the tab is given: the shell hands it a container
that serves none of this computer's venues, so Arm and Disarm are disabled here until they travel to the host (PR 3).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_vps_tab import IVpsTab
from Sagittarius_Elite_Warrior.src.modules.bots.ui.backtest_workbench.backtest_workbench import (
    WorkbenchPorts,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.backtest_workbenches import (
    WorkbenchUnavailableError,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_view import BotsView
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.first_shown import (
    FirstShown,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_consent import (
    TypedVenueConsent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.typed_venue_dialog import (
    ask_typed_venue,
)
from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.vps_command_ids import (
    PrefixedBinder,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.command_binding import (
    ICommandBinder,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.ui.bots_screen.bots_dependencies import (
        BotsDependencies,
    )

NO_BACKTEST_HERE = (
    "The Backtest runs in the Bots tab on this computer. This tab reads nothing at Binance; "
    "the host's candles are for the chart."
)
NO_NEW_BOT_HERE = (
    "Create a bot in the Bots tab and send it with Add to VPS: this tab reads no symbol list "
    "from the exchange."
)


def unavailable_workbench(_venue: TradingVenue) -> WorkbenchPorts:
    raise WorkbenchUnavailableError(NO_BACKTEST_HERE)


def vps_dependencies(tab: IVpsTab, local: BotsDependencies) -> BotsDependencies:
    """`local` with the doors the link gives: what the tab shares with the Bots tab (the thread pool, the kinds, the
    notifier, the time zone) stays."""
    return replace(
        local,
        commands=tab.commands(),
        feeds=tab.candle_feed,
        workbench_ports=unavailable_workbench,
        consent=TypedVenueConsent(ask_typed_venue),
    )


def _opened(tab: IVpsTab, view: BotsView) -> None:
    """The first show starts the link, and the line is drawn again at once (the profile is read now)."""
    tab.opened()
    view.host_line.draw_line()


def vps_arrangement(tab: IVpsTab) -> Callable[[BotsView], None]:
    def arrange(view: BotsView) -> None:
        view.show_host_line(tab.host_line)
        view.model.set_new_bot_unavailable(NO_NEW_BOT_HERE)
        FirstShown(view, lambda: _opened(tab, view))

    return arrange


def vps_binder(binder: ICommandBinder) -> ICommandBinder:
    """The tab's commands carry its own ids (`vps_command_ids.py`)."""
    return PrefixedBinder(binder)
