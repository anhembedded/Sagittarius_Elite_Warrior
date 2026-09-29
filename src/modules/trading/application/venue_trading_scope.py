"""`EPIC-028B` — what a handler acting on one venue needs, resolved once.

@details Every venue-addressed command and query (`ADR` D3) names its venue.
The handler calls `VenueTradingScopes.get(command.venue)` once, at the top,
and reads everything else from the returned scope: the venue's ports and its
session state. This is the single-lookup shape `EmergencyStopCommandHandler`
already used for `TradingVenue.market_type`. No handler can therefore mix
one venue's state with another venue's client.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.venue_context import (
    VenueContext,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


@dataclass(frozen=True)
class VenueTradingScope:
    """One venue's ports and state, taken together."""

    venue: TradingVenue
    ports: VenueContext
    session_state: TradingSessionState
    equity_recorder: EquityCurveRecorder


class VenueTradingScopes:
    """Resolves a `VenueTradingScope` for a venue the configuration serves."""

    def __init__(self, contexts: IVenueContexts, states: VenueSessionStates) -> None:
        self._contexts = contexts
        self._states = states

    def get(self, venue: TradingVenue) -> VenueTradingScope:
        """@raise VenueNotEnabledError `venue` is not served (see
        `IVenueContexts.get()`), before any state is created for it."""
        ports = self._contexts.get(venue)
        return VenueTradingScope(
            venue=venue,
            ports=ports,
            session_state=self._states.session_state(venue),
            equity_recorder=self._states.equity_recorder(venue),
        )
