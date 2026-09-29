"""`EPIC-028C` — one scheduled account refresh per enabled venue, chosen by
that venue's market.

@details Before this, one `PositionRefreshService` ran on the primary venue,
plus a `HoldingsRefreshService` when the primary venue was Spot
(`EPIC-027O`). With Futures and Spot live together each needs its own,
reading its own session state and addressing its own venue, so a Futures
position refresh never asks Spot and a Spot holdings poll never asks
Futures.

What a market refreshes is one entry in `_REFRESH_BY_MARKET`: Futures has
positions; Spot has holdings and no positions (`ITradingClient.
get_positions()` always answers `[]` there, so polling it would be a
wasted request every interval). Plausible extensions, each one entry here
(`architecture-rule.md` §7.2.1): a Futures balance refresh once the account
summary reader exists (`EPIC-028D`); open orders once there is a query for
them (`EPIC-028E`); a third market's own refresh.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.vo.market_type import MarketType
from Sagittarius_Elite_Warrior.src.modules.trading.application.holdings_refresh_service import (
    HoldingsRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.position_refresh_service import (
    PositionRefreshService,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.venue_session_states import (
    VenueSessionStates,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_venue_contexts import (
    IVenueContexts,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from sagittarius_engine.interfaces.i_container import IContainer

VenueRefreshService = PositionRefreshService | HoldingsRefreshService

_RefreshBuilder = Callable[
    [ICommandDispatcher, IEventPublisher, TradingSessionState, TradingVenue],
    VenueRefreshService,
]

_REFRESH_BY_MARKET: dict[MarketType, _RefreshBuilder] = {
    MarketType.FUTURES_USD_M: PositionRefreshService,
    MarketType.SPOT: HoldingsRefreshService,
}


def build_venue_refresh_services(
    container: IContainer,
) -> tuple[VenueRefreshService, ...]:
    """One refresh service per enabled venue, in configuration order; none
    while trading is off (`DISABLED` is never enabled)."""
    dispatcher = container.resolve(ICommandDispatcher)
    publisher = container.resolve(IEventPublisher)
    states = container.resolve(VenueSessionStates)
    return tuple(
        _REFRESH_BY_MARKET[venue.market_type](
            dispatcher, publisher, states.session_state(venue), venue
        )
        for venue in container.resolve(IVenueContexts).enabled()
    )
