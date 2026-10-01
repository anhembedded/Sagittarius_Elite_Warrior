"""`EPIC-028O` — reads `GET /fapi/v1/symbolConfig` and
`GET /fapi/v1/leverageBracket` answers into the port's value types.

@details Shapes per Binance's documented USD-M API, not re-verified against
a live call (egress to `*.binance.*` is blocked in this sandbox), the same
disclosure as `futures_account_control.py`:
- `symbolConfig?symbol=` answers a list of `{symbol, marginType,
  isAutoAddMargin, leverage, maxNotionalValue}`;
- `leverageBracket?symbol=` answers `{symbol, notionalCoef, brackets: [...]}`
  for one symbol, and a list of those without one. Both are accepted, and
  the row for the asked symbol is picked, so a list answer cannot hand back
  another symbol's brackets.

Every function raises `KeyError`, `TypeError`, `ValueError` or
`InvalidOperation` on an answer of another shape; the caller translates them.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    MarginType,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.futures_symbol_setting import (
    FuturesSymbolSetting,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)


def parse_symbol_setting(
    answer: list[dict[str, Any]], symbol: str
) -> FuturesSymbolSetting:
    """@return `symbol`'s row of a `symbolConfig` answer.
    @throws KeyError The answer has no row for `symbol`."""
    row = _row_for(answer, symbol, "symbolConfig")
    return FuturesSymbolSetting(
        symbol=symbol,
        leverage=int(row["leverage"]),
        margin_type=MarginType(str(row["marginType"]).lower()),
        max_notional=Decimal(str(row["maxNotionalValue"])),
    )


def parse_leverage_brackets(
    answer: dict[str, Any] | list[dict[str, Any]], symbol: str
) -> LeverageBrackets:
    """@return `symbol`'s brackets from a `leverageBracket` answer, lowest
    notional first.
    @throws KeyError The answer has no entry for `symbol`."""
    rows = answer if isinstance(answer, list) else [answer]
    entry = _row_for(rows, symbol, "leverageBracket")
    brackets = sorted(
        (_bracket(row) for row in entry["brackets"]),
        key=lambda bracket: bracket.notional_floor,
    )
    return LeverageBrackets(symbol=symbol, brackets=tuple(brackets))


def _row_for(rows: list[dict[str, Any]], symbol: str, endpoint: str) -> dict[str, Any]:
    for row in rows:
        if row["symbol"] == symbol:
            return row
    raise KeyError(f"{endpoint} answered no row for {symbol}")


def _bracket(row: dict[str, Any]) -> LeverageBracket:
    return LeverageBracket(
        bracket=int(row["bracket"]),
        initial_leverage=int(row["initialLeverage"]),
        notional_floor=Decimal(str(row["notionalFloor"])),
        notional_cap=Decimal(str(row["notionalCap"])),
        maintenance_margin_rate=Decimal(str(row["maintMarginRatio"])),
        maintenance_amount=Decimal(str(row["cum"])),
    )
