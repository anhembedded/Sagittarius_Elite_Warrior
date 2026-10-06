"""What the Trade mode needs, resolved once from the container (`EPIC-033I`).

One value (`code/quality.md` §7), built by `trade_dependencies_for`, so the
presenter is constructed with what it needs rather than reaching into the
container, and a test builds the value from fakes: the venues enabled in this
run, each venue's desk dependencies (`desk_dependencies_for`), and where the
chosen venue is remembered.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_trading_ports import (
    IVenueTradingPorts,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.account_tabs.account_tab_confirmations import (
    AccountTabConfirmations,
)
from Sagittarius_Elite_Warrior.src.modules.trading.ui.desk.desk_screen.desk_dependencies import (
    DeskDependencies,
    desk_dependencies_for,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.container_lookup import (
    find_state_coordinator,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.state.ui_state_coordinator import (
    UiStateCoordinator,
)
from sagittarius_engine.interfaces.i_container import IContainer


@dataclass(frozen=True)
class TradeDependencies:
    """The venues, each venue's desk, and the remembered choice."""

    #: The venues enabled in this run, in menu order.
    venues: tuple[TradingVenue, ...]
    #: One venue's desk dependencies, built when its page is.
    desk: Callable[[TradingVenue], DeskDependencies]
    #: Where the chosen venue is remembered; `None` keeps the first.
    state: UiStateCoordinator | None = None
    #: How the account tables ask before a cancel or a close; `None` asks
    #: with the real dialogs.
    confirmations: AccountTabConfirmations | None = None


def trade_dependencies_for(container: IContainer) -> TradeDependencies:
    return TradeDependencies(
        venues=tuple(container.resolve(IVenueTradingPorts).enabled()),
        desk=lambda venue: desk_dependencies_for(container, venue),
        state=find_state_coordinator(container),
    )
