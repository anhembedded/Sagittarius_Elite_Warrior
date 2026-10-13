"""`EPIC-039E` — what laying a Futures ladder asks of the account, from the plan alone.

@details The Futures twin of `LadderNeeds` (`grid_needs.py`): pure numbers the readiness rules
(`futures_rules.py`) compare with the exchange's facts. The executor of `EPIC-039H` builds
it from the plan; a Futures ladder has no opening buy to pay for in quote, it reserves
**margin** against the notional it can reach.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
