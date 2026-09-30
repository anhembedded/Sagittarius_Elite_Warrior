"""`EPIC-028F` — the fake Futures account's per-symbol leverage and margin
mode, and the error bodies Binance answers a change with.

@details Every symbol starts at cross margin, Binance's default for a new
Testnet account. `POST /fapi/v1/leverage` accepts 1 to 125 and answers
`{symbol, leverage, maxNotionalValue}`, refusing anything else with `-4028`;
`POST /fapi/v1/marginType` refuses the mode already in effect with `-4046`.
The notional ceiling is one fixed figure: the fake keeps no leverage
brackets.
"""

from __future__ import annotations

_MAX_LEVERAGE = 125
_MAX_NOTIONAL = "10000000"


class FuturesSymbolConfig:
    """One instance per fake server; a symbol not yet changed is at the
    defaults."""

    def __init__(self) -> None:
        self._leverage: dict[str, int] = {}
        self._margin_type: dict[str, str] = {}

    def change_leverage(self, params: dict[str, str]) -> tuple[int, object]:
        symbol = params["symbol"]
        leverage = int(params["leverage"])
        if not 1 <= leverage <= _MAX_LEVERAGE:
            return 400, {"code": -4028, "msg": f"Leverage {leverage} is not valid"}
        self._leverage[symbol] = leverage
        return 200, {
            "symbol": symbol,
            "leverage": leverage,
            "maxNotionalValue": _MAX_NOTIONAL,
        }

    def change_margin_type(self, params: dict[str, str]) -> tuple[int, object]:
        symbol = params["symbol"]
        wanted = params["marginType"]
        if self._margin_type.get(symbol, "CROSSED") == wanted:
            return 400, {"code": -4046, "msg": "No need to change margin type."}
        self._margin_type[symbol] = wanted
        return 200, {"code": 200, "msg": "success"}
