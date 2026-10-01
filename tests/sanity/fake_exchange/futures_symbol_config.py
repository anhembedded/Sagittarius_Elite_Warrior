"""`EPIC-028F` — the fake Futures account's per-symbol leverage and margin
mode, and the error bodies Binance answers a change with.

@details Every symbol starts at cross margin, Binance's default for a new
Testnet account. `POST /fapi/v1/leverage` accepts 1 to 125 and answers
`{symbol, leverage, maxNotionalValue}`, refusing anything else with `-4028`;
`POST /fapi/v1/marginType` refuses the mode already in effect with `-4046`.

`EPIC-028O` — `GET /fapi/v1/symbolConfig` answers the current setting; a
symbol never changed is at Binance's defaults for a new account (20x, cross).
The notional ceiling comes from the fake's bracket table
(`futures_market.max_notional`).
"""

from __future__ import annotations

from .futures_market import max_notional

_MAX_LEVERAGE = 125
_DEFAULT_LEVERAGE = 20
_DEFAULT_MARGIN_TYPE = "CROSSED"


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
            "maxNotionalValue": str(max_notional(leverage)),
        }

    def symbol_config(self, params: dict[str, str]) -> tuple[int, object]:
        symbol = params["symbol"]
        leverage = self._leverage.get(symbol, _DEFAULT_LEVERAGE)
        return 200, [
            {
                "symbol": symbol,
                "marginType": self._margin_type.get(symbol, _DEFAULT_MARGIN_TYPE),
                "isAutoAddMargin": "false",
                "leverage": leverage,
                "maxNotionalValue": str(max_notional(leverage)),
            }
        ]

    def change_margin_type(self, params: dict[str, str]) -> tuple[int, object]:
        symbol = params["symbol"]
        wanted = params["marginType"]
        if self._margin_type.get(symbol, _DEFAULT_MARGIN_TYPE) == wanted:
            return 400, {"code": -4046, "msg": "No need to change margin type."}
        self._margin_type[symbol] = wanted
        return 200, {"code": 200, "msg": "success"}
