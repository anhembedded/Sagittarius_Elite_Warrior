"""`EPIC-035T` — what a rung does when its order is refused for its own numbers.

A counter order the exchange (or trading, before the request) refuses for its
quantity, price or notional is one rung's problem, not the ladder's. The rung stays
EMPTY, remembers when it was refused, and the ladder goes on with a reason that
names it. The rule for a ladder that keeps failing is the one that already exists
for a rung whose order keeps ending (`LEVEL_END_WINDOW`, `LEVEL_KEEPS_ENDING`), held
over the **whole ladder**: a second refusal on any rung within the window halts the
bot. A cause that is the account's, not the order's (`-2010` is also "insufficient
balance"), refuses every rung once; a per-rung count would let the ladder bleed to
all-EMPTY while RUNNING. An order that ended elsewhere inside the window counts too:
the guard errs towards halting, which is the safe side.

The lost counter order is a price knowingly paid (`architecture-rule.md` §7.1):
until a neighbour's fill owes that rung an order again it rests nothing, and the
base it would have sold, or the quote it would have spent, waits. The reason on the
bot says so. `test_grid_counter_order_rejection.py` locks the behaviour.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    LEVEL_END_WINDOW,
    Halt,
    PlaceOrder,
    Reaction,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)


def rejected_counter(
    runtime: GridRuntime, order: PlaceOrder, at: datetime, detail: str
) -> Reaction:
    """The ladder after `order` was refused at `at`: its rung EMPTY and noted, or
    a halt when any rung was refused or ended already within `LEVEL_END_WINDOW`."""
    level = runtime.levels[order.level_index]
    kept = tuple(t for t in level.ended_at if at - t < LEVEL_END_WINDOW)
    after = runtime.with_level(replace(level, ended_at=(*kept, at)))
    if any(at - t < LEVEL_END_WINDOW for lv in runtime.levels for t in lv.ended_at):
        halt = Halt(
            GridReason.LEVEL_KEEPS_ENDING,
            f"L{level.index}: a second order was refused or ended within a minute; "
            f"{detail}",
        )
        return Reaction(after.with_reason(halt.reason, halt.detail), (halt,))
    return Reaction(after.with_reason(GridReason.COUNTER_ORDER_REJECTED, detail))
