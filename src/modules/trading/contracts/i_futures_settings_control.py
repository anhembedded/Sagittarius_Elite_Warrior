"""`EPIC-028I` — port: a desk's leverage and margin-mode chips.

@details Bound to one venue, like every port in `VenueTradingPorts`. Each
method sends `EPIC-028F`'s venue-addressed command and answers with what the
exchange confirmed, or why it refused: an open position on the symbol, a
safety gate, the exchange's own refusal. On Spot every change answers
`AccountControlRefusal.NOT_A_FUTURES_VENUE` without a request.

Both are network writes, so a caller runs them off the UI thread.

Plausible extensions, each one method here plus its command:
- the position mode (one-way or hedge);
- the Multi-Assets mode.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)


class IFuturesSettingsControl(ABC):
    """Changes a symbol's leverage or margin mode on one venue."""

    @abstractmethod
    def change_leverage(
        self, symbol: str, leverage: int
    ) -> AccountControlResult[LeverageSetting]:
        """Set `symbol`'s initial leverage; the answer carries the leverage
        in effect and the notional it allows."""

    @abstractmethod
    def change_margin_type(
        self, symbol: str, margin_type: MarginType
    ) -> AccountControlResult[MarginType]:
        """Set `symbol`'s margin mode, cross or isolated."""
