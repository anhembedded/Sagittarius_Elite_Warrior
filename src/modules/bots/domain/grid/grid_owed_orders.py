"""`BUG-266` - the orders a Grid owes the exchange are on record before they are sent.

The pairing of a counter SELL (the BUY it completes) lives only in the bot's own record. A
reaction hands the executor its runtime and the orders to send; the executor saves the runtime
and then sends. Were the order sent and the process to die (or the request to raise while the
order is live) before the placement is saved, the restart's reconcile would adopt a live order
with no pairing (`grid_reactions.adopted`), and its fill would close no cycle: Cycles and Grid
profit come out short, Total PnL does not move.

So the runtime saved *with* the reaction also lists each order about to be sent as owed, in
`held` (the record a pause already uses for an order the bot owes and has not placed). The
placer settles an entry when the outcome is known: the level holds the order, or a definite
answer says nothing was placed. A `FAULT` may be live and is not settled: `adopted` finds the
entry's pairing, and a resume places the order if it never reached the exchange.

Limit: a fault on one order halts the bot, so the orders after it in the same reaction are never
sent; they stay on record as owed, and a resume places them. An order that reached the exchange
while the app was down and filled there is not found by the reconcile (it lists open orders); the
inventory check halts the bot on the difference, as it did before this entry existed.
"""

from __future__ import annotations

from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    GridAction,
    PlaceOrder,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridRuntime,
    HeldOrder,
)


def owing(runtime: GridRuntime, actions: tuple[GridAction, ...]) -> GridRuntime:
    """`runtime` with every order in `actions` listed as owed, one entry per level."""
    for action in actions:
        if isinstance(action, PlaceOrder):
            runtime = _with_entry(runtime, action)
    return runtime


def settled_intent(runtime: GridRuntime, level_index: int) -> GridRuntime:
    """`runtime` without the entry `owing` wrote for `level_index`: the outcome is known."""
    return replace(
        runtime, held=tuple(h for h in runtime.held if h.level_index != level_index)
    )


def _with_entry(runtime: GridRuntime, action: PlaceOrder) -> GridRuntime:
    kept = tuple(h for h in runtime.held if h.level_index != action.level_index)
    entry = HeldOrder(
        action.level_index,
        action.side,
        action.quantity,
        action.paired_buy_price,
        action.paired_buy_fee_quote,
        action.carried_executed,
        action.carried_base_fee,
    )
    return replace(runtime, held=(*kept, entry))
