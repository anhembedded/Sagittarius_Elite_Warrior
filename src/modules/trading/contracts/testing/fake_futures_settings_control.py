"""`EPIC-028I` — `IFuturesSettingsControl`'s verified fake.

@details By default the exchange accepts every change and confirms it
(a leverage change allows `max_notional`). `refuses_with` makes every later
change answer that refusal instead, as an open position or the exchange
would. Every change asked for is recorded.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.account_control_result import (
    AccountControlRefusal,
    AccountControlResult,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_settings_control import (
    IFuturesSettingsControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)


class FakeFuturesSettingsControl(IFuturesSettingsControl):
    """A venue that applies what it is asked, unless told to refuse."""

    def __init__(self, max_notional: Decimal = Decimal(1_000_000)) -> None:
        self._max_notional = max_notional
        self._refusal: tuple[AccountControlRefusal, str] | None = None
        #: `(symbol, leverage)` per `change_leverage` call.
        self.leverage_changes: list[tuple[str, int]] = []
        #: `(symbol, margin_type)` per `change_margin_type` call.
        self.margin_changes: list[tuple[str, MarginType]] = []

    def refuses_with(self, refusal: AccountControlRefusal, detail: str) -> None:
        self._refusal = (refusal, detail)

    def change_leverage(
        self, symbol: str, leverage: int
    ) -> AccountControlResult[LeverageSetting]:
        self.leverage_changes.append((symbol, leverage))
        if self._refusal is not None:
            return AccountControlResult(self._refusal[0], None, self._refusal[1])
        return AccountControlResult(
            None, LeverageSetting(symbol, leverage, self._max_notional)
        )

    def change_margin_type(
        self, symbol: str, margin_type: MarginType
    ) -> AccountControlResult[MarginType]:
        self.margin_changes.append((symbol, margin_type))
        if self._refusal is not None:
            return AccountControlResult(self._refusal[0], None, self._refusal[1])
        return AccountControlResult(None, margin_type)
