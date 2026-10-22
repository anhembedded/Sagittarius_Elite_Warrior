"""`BUG-266` - the orders a Grid owes the exchange are on record before they are sent.

The pairing of a counter SELL (the BUY it completes) lives only in the bot's own record. A
reaction hands the executor its runtime and the orders to send; the executor saves the runtime
and then sends. Were the order sent and the process to die before the placement is saved, the restart's reconcile would adopt a live order
with no pairing (`grid_reactions.adopted`), and its fill would close no cycle: Cycles and Grid
profit come out short, Total PnL does not move.

So the runtime saved *with* the reaction also lists each order about to be sent as owed, in
`held` (the record a pause already uses for an order the bot owes and has not placed). The
placer settles an entry in the save that records the outcome: the level holds the order, or a
refusal, a pause or a fault says nothing is on the ladder. What it covers is a **death between the
send and that save**: the restart is RECOVERING, the reconcile adopts the live order and
`adopted` takes the pairing from the entry, or `release_held` places the order if it never
reached the exchange. A request that raised (`FAULT`) is not that case: the bot goes to ERROR,
whose only exit is a Stop that cancels the order, so its entry is settled like any other.

Limit: a refusal or fault on one order stops the reaction, so the orders after it are never sent;
their entries stay on record as owed, and die with the re-plan a halt or a Stop leads to. An order that reached the exchange
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
