"""`EPIC-039C` — the fake Futures account's settings, and when Binance refuses to change them.

@details Error codes and texts are Binance's (the error-code page, read 2026-10-13):
`-4047` margin type cannot be changed with open orders, `-4048` with a position (`-4046`,
no need to change, is `FuturesSymbolConfig`'s), `-4161` leverage reduction is not
supported in isolated mode with open positions, `-4067`/`-4068` position side cannot be
changed with open orders / a position. Position mode is one account-wide setting, One-way
until a test changes it.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from .futures_account_state import FuturesAccountState
from .futures_algo_orders import FuturesAlgoOrders
from .futures_symbol_config import FuturesSymbolConfig

_MAX_LEVERAGE = 125


def _refusal(code: int, message: str) -> tuple[int, dict[str, Any]]:
    return 400, {"code": code, "msg": message}


class AccountSettings:
    """Leverage, margin type and position mode, over the book's orders and the account."""

    def __init__(
        self,
        resting: Mapping[str, dict[str, Any]],
        algo: FuturesAlgoOrders,
        account: FuturesAccountState,
        symbol_config: FuturesSymbolConfig,
    ) -> None:
        self._resting = resting
        self._algo = algo
        self._account = account
        self._symbol_config = symbol_config
        self._dual_side = False

    @property
    def dual_side(self) -> bool:
        """Whether the account is in Hedge mode (`EPIC-037E`: `-4061` reads it)."""
        return self._dual_side

    def change_leverage(self, params: dict[str, str]) -> tuple[int, object]:
        """`POST /fapi/v1/leverage`."""
        symbol = params["symbol"]
        leverage = int(params["leverage"])
        reducing = leverage < self._symbol_config.leverage(symbol)
        if (
            1 <= leverage <= _MAX_LEVERAGE
            and reducing
            and self._account.positions.amount(symbol) != 0
            and self._account.positions.isolated(symbol)
        ):
            return _refusal(
                -4161,
                "Leverage reduction is not supported in Isolated Margin Mode "
                "with open positions.",
            )
        return self._symbol_config.change_leverage(params)

    def change_margin_type(self, params: dict[str, str]) -> tuple[int, object]:
        """`POST /fapi/v1/marginType`."""
        symbol = params["symbol"]
        if self._symbol_config.margin_type(symbol) != params["marginType"]:
            has_orders = any(o["symbol"] == symbol for o in self._resting.values())
            if has_orders or self._algo.open_orders(symbol):
                return _refusal(
                    -4047, "Margin type cannot be changed if there exists open orders."
                )
            if self._account.positions.amount(symbol) != 0:
                return _refusal(
                    -4048, "Margin type cannot be changed if there exists position."
                )
        return self._symbol_config.change_margin_type(params)

    def position_mode(self, params: dict[str, str]) -> tuple[int, object]:
        """`GET /fapi/v1/positionSide/dual`."""
        return 200, {"dualSidePosition": self._dual_side}

    def set_position_mode(self, params: dict[str, str]) -> tuple[int, object]:
        """`POST /fapi/v1/positionSide/dual`: refused for every symbol, as the
        setting is account-wide."""
        if self._resting or self._algo.open_orders(None):
            return _refusal(
                -4067, "Position side cannot be changed if there exists open orders."
            )
        if self._account.positions.symbols():
            return _refusal(
                -4068, "Position side cannot be changed if there exists position."
            )
        self._dual_side = str(params["dualSidePosition"]).lower() == "true"
        return 200, {"code": 200, "msg": "success"}
