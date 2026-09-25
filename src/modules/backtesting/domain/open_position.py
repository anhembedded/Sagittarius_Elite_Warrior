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
`BOT-049` adds a second, structural one the same way: `MarginRiskPolicy`'s
`ILiquidatablePosition` (a `Protocol` — `§2` already forbids a second ABC base
on a class that already has one).
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
    #: BOT-049 — `None` for an unleveraged (1.0x) LONG (modeled as spot, see
    #: `MarginRiskPolicy.liquidation_price`'s own docstring); always set
    #: otherwise. Implements `MarginRiskPolicy.ILiquidatablePosition`.
    liquidation_price: float | None = None
    #: BOT-106B — worst/best unrealized `pnl_percent` (same sign and same
    #: percent-of-margin convention as `Trade.pnl_percent`) seen at any point
    #: while this position was open, updated every bar by
    #: `PaperExchange.check_intrabar_stops()` from that bar's `high`/`low`.
    #: `0.0` until the first bar after entry updates them — a position closed
    #: without ever seeing a subsequent bar (rare: same-bar entry and exit)
    #: keeps both at `0.0`, which is correct: no excursion was ever observed.
    mae_percent: float = 0.0
    mfe_percent: float = 0.0
    #: BOT-105A — `True` once `PaperExchange` has moved this position's
    #: `stop_loss_price` to break-even; guards the move as one-time, since
    #: a not-yet-triggered `stop_loss_price` always sits on the losing
    #: side of `entry_price` (`OrderMatchingPolicy.calculate_stop_loss_price`),
    #: so re-arming would never move it anywhere new.
    break_even_armed: bool = False
    #: BOT-105A — `True` once this position's trailing stop has armed
    #: (`mfe_percent` reached `trailing_activation_pct`); guards whether
    #: `trailing_peak_price` is tracking yet, distinct from `break_even_armed`
    #: since a run can configure either, both, or neither independently.
    trailing_armed: bool = False
    #: BOT-105A — best price seen since the trailing stop armed (a running
    #: high for LONG, a running low for SHORT), independent of `mfe_percent`
    #: so ratcheting `stop_loss_price` needs no leverage/margin inversion —
    #: `None` until armed.
    trailing_peak_price: float | None = None
