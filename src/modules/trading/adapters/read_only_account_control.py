"""`EPIC-035H` — a Futures account's leverage and margin mode, for a read-only copy.

`FuturesAccountControl` talks to the exchange through the session factory, not
through a trading client, so the read-only client factory does not reach it. A
leverage or margin-mode change alters the account the first copy's ladder trades
under, so a read-only copy refuses both and reads as before.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.i_futures_account_control import (
    IFuturesAccountControl,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_setting import (
    LeverageSetting,
)


class ReadOnlyAccountControl(IFuturesAccountControl):
    """Reads through; changes nothing."""

    def __init__(self, inner: IFuturesAccountControl, reason: str) -> None:
        self._inner = inner
        self._reason = reason

    def open_position(self, symbol: str) -> Decimal:
        return self._inner.open_position(symbol)

    def symbol_setting(self, symbol: str) -> FuturesSymbolSetting:
        return self._inner.symbol_setting(symbol)

    def leverage_brackets(self, symbol: str) -> LeverageBrackets:
        return self._inner.leverage_brackets(symbol)

    def change_leverage(self, symbol: str, leverage: int) -> LeverageSetting:
        raise ReadOnlyInstanceError(self._reason)

    def change_margin_type(self, symbol: str, margin_type: MarginType) -> MarginType:
        raise ReadOnlyInstanceError(self._reason)
