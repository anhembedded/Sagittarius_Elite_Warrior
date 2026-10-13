"""`EPIC-039E` — port: make the venue match the bot's parameters, and prove it still does.

@details Before the first order a Futures bot needs its symbol's margin type and leverage to
be the ones its parameters name, on an account in One-way mode. `ensure` is a precondition
and a postcondition in one: read, change only what differs, **read back**, compare. Spot has
nothing to ensure and answers `ENSURED` without a request. `verify` is the read-only half,
for a running bot: someone changing leverage in the Binance app is a drift, not something the
bot silently sets again.

Both are network reads (`ensure` also writes), so a caller runs them off the UI thread. The
gate never changes the account's position mode: it is account-wide, and another bot or the
owner's desk may be using it.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.venue_settings_gate_result import (
    GateRequest,
    GateResult,
)


class IVenueSettingsGate(ABC):
    @abstractmethod
    def ensure(self, request: GateRequest) -> GateResult:
        """Make `request.symbol` hold the asked settings and answer what the exchange
        confirmed, or why it does not."""

    @abstractmethod
    def verify(self, request: GateRequest) -> GateResult:
        """Read the settings and compare them with `request`; change nothing."""
