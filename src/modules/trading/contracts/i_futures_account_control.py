"""`EPIC-028F` — changes a USD-M Futures symbol's leverage and margin mode.

@details Its own port rather than two more methods on `ITradingClient`,
which Spot implements too and would have to refuse (Interface Segregation,
`architecture-rule.md` §1). A Spot `VenueContext` holds no implementation of
it, so "this venue has no leverage" is a type the handlers read, not a
runtime error.

Both changes are account settings, not orders. The app refuses both for a
symbol with an open position, its own policy (`account_control_gate.py`
says why and what Binance itself refuses). `ChangeLeverageCommandHandler` and
`ChangeMarginTypeCommandHandler` check that first through `open_position`,
which is on this port so that the read fails the way the changes do: every
failure is one of the port's two errors, never the SDK's (PR #299 review,
finding 1).

`EPIC-028O` adds the two reads a desk needs before it offers a change: the
current setting (`GET /fapi/v1/symbolConfig`, since `positionRisk` v3 no
longer carries it, `BUG-114`) and the leverage brackets
(`GET /fapi/v1/leverageBracket`), which cap the leverage slider and give the
liquidation estimate its maintenance rate. Both are signed reads of this
account's settings, so they live here and fail the way the changes do.

Plausible extensions, each one method here and one in the adapter: adding or
removing isolated margin (`POST /fapi/v1/positionMargin`); the Multi-Assets
mode (`GET /fapi/v1/multiAssetsMargin`).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)


class IFuturesAccountControl(ABC):
    """One Futures account's per-symbol leverage and margin mode."""

    @abstractmethod
    def open_position(self, symbol: str) -> Decimal:
        """@brief The signed size of `symbol`'s open position: positive long,
        negative short, zero when flat.
        @throws AccountControlRejectedError The exchange refused the read.
        @throws AccountControlUnavailableError The exchange never answered,
        or its answer could not be read."""

    @abstractmethod
    def symbol_setting(self, symbol: str) -> FuturesSymbolSetting:
        """@brief `symbol`'s leverage and margin mode now.
        @throws AccountControlRejectedError The exchange refused the read.
        @throws AccountControlUnavailableError The exchange never answered,
        or its answer could not be read."""

    @abstractmethod
    def leverage_brackets(self, symbol: str) -> LeverageBrackets:
        """@brief `symbol`'s notional and leverage brackets for this account.
        @throws AccountControlRejectedError The exchange refused the read.
        @throws AccountControlUnavailableError The exchange never answered,
        or its answer could not be read."""

    @abstractmethod
    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        """@brief Sets `symbol`'s initial leverage.
        @return The leverage the exchange confirmed and the notional it
        allows.
        @throws AccountControlRejectedError The exchange refused.
        @throws AccountControlUnavailableError The outcome is unknown: the
        exchange never answered, or its answer could not be read."""

    @abstractmethod
    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        """@brief Sets `symbol`'s margin mode.
        @return The mode now in effect; asking for the mode already in
        effect is not an error.
        @throws AccountControlRejectedError The exchange refused.
        @throws AccountControlUnavailableError The outcome is unknown: the
        exchange never answered."""
