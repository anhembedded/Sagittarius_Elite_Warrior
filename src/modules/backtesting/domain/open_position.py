"""One simulated position, as a record — PR 3.1c-2.

It left `paper_exchange.py` with the split that file's 472 lines forced
(`EPIC-025D` §5.5, `architecture-rule.md` §5 rule 4), and it is the third thing
that file was holding rather than an afterthought of the other two: a position
*record* is pure data with no behaviour, `FillPricing` is arithmetic, and
`PaperExchange` is the books. Each changes for its own reason — a new field here
(funding, a partial fill) touches none of the other two.

@par It is `OpenPosition` now, not `_OpenPosition`
A leading underscore says *private to this module*, and two modules import it,
so the underscore was about to become a lie. The name it must **not** collapse
into is `trading`'s `LivePosition`: that one is a real exchange's answer about
real money, this one is a number the app mutates on every candle, and HLD §1 C3
keeps them apart deliberately. `Docs/VOCABULARY` carries both rows.

`IStoppablePosition` is the contract that lets `OrderMatchingPolicy` evaluate
stops without knowing what a paper position is; this is its sole implementer.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from Sagittarius_Elite_Warrior.src.modules.backtesting.domain.policies.order_matching_policy import (
    IStoppablePosition,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.position_side import (
    PositionSide,
)


@dataclass
class OpenPosition(IStoppablePosition):
    quantity: float
    entry_price: float
    entry_time: datetime
    balance_before_entry: float
    entry_fee: float
    entry_reason: str
    entry_metadata: Mapping[str, Any] = field(default_factory=dict)
    stop_loss_price: float | None = None
    take_profit_price: float | None = None
    side: PositionSide = PositionSide.LONG
    leverage: float = 1.0
