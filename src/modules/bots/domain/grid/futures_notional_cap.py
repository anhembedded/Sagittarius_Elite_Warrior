"""`EPIC-039F` / `EPIC-039H` — the largest position a symbol allows at a leverage.

@details Binance sizes leverage by notional band: the higher the notional, the lower the leverage
allowed. A position of a given leverage may be as large as the cap of the highest bracket that still
allows that leverage. One function, so the plan-time guard (`NOTIONAL_ABOVE_BRACKET`), the readiness
rule and the owner budget a Futures bot registers agree on one number.
"""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBrackets,
)


def allowed_notional(brackets: LeverageBrackets, leverage: int) -> Decimal:
    """The largest notional `brackets` allow at `leverage`; zero when none allows it."""
    return max(
        (b.notional_cap for b in brackets.brackets if b.initial_leverage >= leverage),
        default=Decimal(0),
    )
