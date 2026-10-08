"""`EPIC-035M` — what a Grid has earned: the total first, its parts beside it.

Pure `Decimal` arithmetic over the saved run. The **total** is the realised PnL of
every sell (a completed cycle, the sell of the opening inventory, an exit slice,
each against the average cost and net of fees) plus the unrealised PnL of what is
still held at the bot's own last price. **Grid profit** is one part of it: the
completed buy/sell cycles only. The **HODL benchmark** is what the same capital
would have gained held from the price the run began at.

A figure that needs a price the bot has not heard is `None`, never a zero.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)

_ZERO = Decimal(0)


@dataclass(frozen=True, slots=True)
class PnlSummary:
    """A run's earnings in the quote asset."""

    #: Realised plus unrealised; `None` while the unrealised cannot be judged.
    total: Decimal | None
    #: Every sell against the average cost, net of fees.
    realised: Decimal
    #: What is held, at the bot's own price; `None` without a price.
    unrealised: Decimal | None
    #: The completed buy/sell cycles, one part of the total.
    grid_profit: Decimal
    #: The same capital held from the start price, at the bot's own price.
    hodl: Decimal | None
    #: Fills whose fee could not be priced: the figures are short by them.
    unpriced_fees: int


def pnl_summary(runtime: GridRuntime, capital: Decimal) -> PnlSummary:
    unrealised = _unrealised(runtime)
    return PnlSummary(
        total=None if unrealised is None else runtime.realised_total + unrealised,
        realised=runtime.realised_total,
        unrealised=unrealised,
        grid_profit=runtime.realised_profit,
        hodl=_hodl(runtime, capital),
        unpriced_fees=runtime.unpriced_fees,
    )


def _unrealised(runtime: GridRuntime) -> Decimal | None:
    if runtime.inventory <= 0:
        return _ZERO
    average = runtime.average_cost
    if runtime.mark_price is None or average is None:
        return None
    return runtime.inventory * (runtime.mark_price - average)


def _hodl(runtime: GridRuntime, capital: Decimal) -> Decimal | None:
    start, mark = runtime.start_price, runtime.mark_price
    if start is None or mark is None or start <= 0:
        return None
    return capital / start * mark - capital
