"""`EPIC-027F` — port for the one place allowed to construct an
`ITradingClient` adapter.

@details Before this port existed, six call sites each constructed
`FuturesTradingClient(...)` directly (`architecture-rule.md` §7.2.1's closed-
design tell: adding a second venue meant editing all six). Every one of them
already receives `ITradingSessionFactory`/`IExchangeCredentialsProvider`/
`IMarketMetadataProvider` as constructor-injected collaborators purely to
build that one client with a call-site-specific `OrderSubmissionMode` — a
fixed-mode `ITradingClient` singleton (bound only when `TradingVenue !=
DISABLED`) cannot serve them, since `ExecuteOrderCommandHandler` and
`EmergencyStopCommandHandler` need `LIVE` while the others need
`VALIDATE_ONLY`.

This factory owns those three raw collaborators instead, and hands back a
client for whichever `OrderSubmissionMode` the caller needs. `venue` is not a
parameter here: exactly one concrete factory is bound per process (today,
always `FuturesTradingClientFactory` — `TradingVenue` has no second tradeable
member yet), matching how `ITradingSessionFactory` itself is not
venue-parameterized either. `EPIC-027K` adds Spot by binding a second
concrete factory behind this same port when a Spot venue exists to select
between (`architecture-rule.md` §7.2.1: the seam now, the variant later).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_trading_client import (
    ITradingClient,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_submission_mode import (
    OrderSubmissionMode,
)


class ITradingClientFactory(ABC):
    """Port for the one place allowed to construct an `ITradingClient`
    adapter — every consumer asks for one by `OrderSubmissionMode`, never by
    constructing the concrete adapter itself."""

    @abstractmethod
    def create(self, mode: OrderSubmissionMode) -> ITradingClient:
        """@brief A trading client ready to place/cancel orders and read
        positions, submitting under `mode`.
        @details Returns a fresh client per call (matching every call site's
        pre-existing behaviour) — never a shared instance, since two callers
        wanting different `mode`s could otherwise observe each other's."""
