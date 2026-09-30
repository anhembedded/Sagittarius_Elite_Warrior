"""`EPIC-028F` — changes a USD-M Futures symbol's leverage and margin mode.

@details Its own port rather than two more methods on `ITradingClient`,
which Spot implements too and would have to refuse (Interface Segregation,
`architecture-rule.md` §1). A Spot `VenueContext` holds no implementation of
it, so "this venue has no leverage" is a type the handlers read, not a
runtime error.

Both changes are account settings, not orders, and Binance refuses them for
a symbol with an open position. `ChangeLeverageCommandHandler` and
`ChangeMarginTypeCommandHandler` check that first; this port only carries
the request and the answer.

Plausible extensions, each one method here and one in the adapter: reading
the current setting (`GET /fapi/v1/symbolConfig`, since `positionRisk` v3
no longer carries it, `BUG-114`); the leverage brackets
(`GET /fapi/v1/leverageBracket`) so a desk can cap its slider; adding or
removing isolated margin (`POST /fapi/v1/positionMargin`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)


class IFuturesAccountControl(ABC):
    """One Futures account's per-symbol leverage and margin mode."""

    @abstractmethod
    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        """@brief Sets `symbol`'s initial leverage.
        @return The leverage the exchange confirmed and the notional it
        allows.
        @throws AccountControlRejectedError The exchange refused.
        @throws AccountControlUnavailableError The exchange never answered."""

    @abstractmethod
    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        """@brief Sets `symbol`'s margin mode.
        @return The mode now in effect; asking for the mode already in
        effect is not an error.
        @throws AccountControlRejectedError The exchange refused.
        @throws AccountControlUnavailableError The exchange never answered."""
