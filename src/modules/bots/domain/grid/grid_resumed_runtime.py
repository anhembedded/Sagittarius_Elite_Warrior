"""`BUG-268` - the runtime a resume lays its fresh ladder into: the run goes on.

A resume (the person's, or the recovery run's `condition_cleared`, `EPIC-042C`) cancels the old
ladder and lays one sized from the price now (ADR D13). What it replaces is the **ladder**, never
the run: everything the run has earned, paid and recorded is carried by default, and only the
fields named in `LADDER_FIELDS` come from the new ladder. The rule is inverted on purpose: a field
added to `GridRuntime` later is kept across a resume without anyone remembering to list it. The
list it replaced named what to keep, and dropped `commissions`, `funding_total` and
`protective_stops` because nobody added them.

The holding: the inventory trading derived from the exchange is what the bot holds now (D6). Its
cost is taken only when the quantity differs from the run's own: trading's cost is the quote paid
without the quote fees the buys paid (`inventory_after`), while the run's cost carries the fee each buy paid
(`grid_books`), so replacing an unchanged holding's cost would drop those fees from the basis
and overstate every later sell's profit. A quantity that differs (a fill while the ladder was
cancelled, a stop that closed part of it) has no cost in the run's own books, and trading's is
the one there is.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

#: What the fresh ladder owns: its levels, nothing owed yet, the direction it trades, and no
#: halt reason or stop in progress (the bot is about to run).
LADDER_FIELDS = frozenset(
    {
        "levels",
        "held",
        "entry_side",
        "reason",
        "reason_detail",
        "sell_base_on_stop",
        # The best price heard while waiting belongs to one wait; a resume is a new entry
        # (`BUG-276`, ADR 046 D3), so the fresh ladder's `None` replaces an earlier wait's.
        "waiting_best_price",
    }
)


def resumed_runtime(
    earned: GridRuntime, ladder: GridRuntime, holding: OwnerInventory
) -> GridRuntime:
    """`earned` with `ladder`'s levels, holding `holding`; the run's start price stays its own."""
    cost = earned.cost if holding.quantity == earned.inventory else holding.cost
    return replace(
        earned,
        levels=ladder.levels,
        held=ladder.held,
        entry_side=ladder.entry_side,
        reason=ladder.reason,
        reason_detail=ladder.reason_detail,
        sell_base_on_stop=ladder.sell_base_on_stop,
        waiting_best_price=ladder.waiting_best_price,
        inventory=holding.quantity,
        cost=cost,
        start_price=earned.start_price or ladder.start_price,
    )
