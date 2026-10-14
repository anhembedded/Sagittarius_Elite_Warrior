"""`EPIC-039E` — what laying a Futures ladder asks of the account, from the plan alone.

@details The Futures twin of `LadderNeeds` (`grid_needs.py`): pure numbers the readiness rules
(`futures_rules.py`) compare with the exchange's facts. The executor of `EPIC-039H` builds
it from the plan; a Futures ladder has no opening buy to pay for in quote, it reserves
**margin** against the notional it can reach.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.leverage_brackets import (
    LeverageBracket,
    LeverageBrackets,
)


@dataclass(frozen=True, slots=True)
class FuturesNeeds:
    #: The initial margin the plan's worst case reserves: its worst-case notional divided by
    #: the leverage, plus nothing the exchange adds on its own (fees come from the cost model).
    initial_margin: Decimal
    #: The largest position notional the ladder can reach (`EPIC-039B`'s worst case).
    worst_case_notional: Decimal
    #: The leverage the bot asked for.
    leverage: int

    def __post_init__(self) -> None:
        if self.initial_margin < 0 or self.worst_case_notional < 0:
            raise ValueError("a ladder never needs a negative amount")
        if self.leverage < 1:
            raise ValueError(f"leverage must be 1 or more, got {self.leverage}")


def bracket_below_leverage(
    brackets: LeverageBrackets, worst_case_notional: Decimal, leverage: int
) -> LeverageBracket | None:
    """The bracket `worst_case_notional` falls in when it allows less than `leverage`, else
    `None`. The one comparison the Start gate (`leverage_above_bracket`) and the backtest
    (`bracket_refusal`) both make, so they cannot disagree on what a bracket allows."""
    bracket = brackets.bracket_for(worst_case_notional)
    return bracket if leverage > bracket.initial_leverage else None
