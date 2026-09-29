"""`EPIC-028B` — each trading venue's own session state, owned in one place.

@details `TradingSessionState` (the trading switch, order counters, symbol
leases, the Spot baseline) and `EquityCurveRecorder` are application state,
so the application layer owns them, one of each per venue. Two consumers
read the same instances through here:
- `VenueAssembly` (composition) wires a venue's own state into that venue's
  user data stream.
- `VenueTradingScopes` hands it to every handler that acts on a venue.

That is why this is its own class rather than a field of `VenueContext`,
which holds ports only and lives in `contracts/`. `contracts/` may not import
application state.

Nothing here checks whether a venue is enabled: `IVenueContexts.get()` is
where that refusal happens, and every handler asks it first
(`VenueTradingScopes.get()`).
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.trading.application.equity_curve_recorder import (
    EquityCurveRecorder,
)
from Sagittarius_Elite_Warrior.src.modules.trading.application.trading_session_state import (
    TradingSessionState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)


class VenueSessionStates:
    """One `TradingSessionState` and one `EquityCurveRecorder` per venue,
    built on first use and the same instance on every later call."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._session_states: dict[TradingVenue, TradingSessionState] = {}
        self._equity_recorders: dict[TradingVenue, EquityCurveRecorder] = {}

    def session_state(self, venue: TradingVenue) -> TradingSessionState:
        with self._lock:
            state = self._session_states.get(venue)
            if state is None:
                state = TradingSessionState()
                self._session_states[venue] = state
            return state

    def equity_recorder(self, venue: TradingVenue) -> EquityCurveRecorder:
        with self._lock:
            recorder = self._equity_recorders.get(venue)
            if recorder is None:
                recorder = EquityCurveRecorder()
                self._equity_recorders[venue] = recorder
            return recorder
