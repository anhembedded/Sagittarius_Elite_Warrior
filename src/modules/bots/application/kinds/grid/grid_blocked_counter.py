"""`BUG-225` — a counter order that finds its level occupied asks the exchange before it halts.

A full fill owes its counter order to the neighbouring level, which in a healthy ladder is empty
at that moment. When the price fell through two adjacent rungs and the user-data stream handed
the app the lower rung's fill before the higher one's, the ledger still holds the higher rung's
order (the exchange has filled it; the app has not been told) and `on_fill` answers
`DUPLICATE_LEVEL_ORDER`: a halt that on Futures closes a healthy position at market. Before it
stands, the order in the way is read once from the exchange (`find_order`, never cached):

  · **filled**: the fill that owes the counter is *parked* and replayed right after the order's
    own fill is applied, so the fills are applied in the order the exchange made them. Nothing is
    applied from history: trading's owner book learns a fill only from the stream, and a counter
    SELL placed before it had would be refused as exceeding the inventory it knows;
  · **cancelled or expired** with nothing executed: the level is freed and the counter retried
    (the stream's end event for an order the ladder no longer holds changes nothing);
  · **still open**, or the exchange cannot say: a genuine duplicate, the halt stands unchanged.

`on_fill` stays pure and the read happens once per blocked counter, never in a loop. A parked fill
lives in memory only: a restart or a stream gap reconciles from the exchange's history, which
applies both fills in order (`BUG-214`), and `on_fill` ignores a fill for an order the ledger no
longer holds, so a parked fill the reconcile applied is not replayed twice.
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    Halt,
    LevelFill,
    Reaction,
    drop_order,
    on_fill,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_status import (
    OrderStatus,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The statuses of an order the exchange ended without filling it.
_ENDED_UNFILLED = frozenset(
    {OrderStatus.CANCELED, OrderStatus.EXPIRED, OrderStatus.REJECTED}
)


class GridBlockedCounter:
    """Reacts to a fill, settling the order in its counter's way when there is one."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        #: Fills waiting for the fill of the order their counter's level holds, by that order.
        self._parked: dict[str, list[LevelFill]] = {}

    def on_fill(self, fill: LevelFill) -> Reaction:
        """`on_fill` of the bot's ladder; its actions are what the placer must send."""
        state = self._context.state
        hold = state.state is not BotLifecycleState.RUNNING
        reaction = on_fill(state.runtime, fill, self._context.terms.step_size, hold)
        blocked = _blocked_level(reaction)
        if blocked is None:
            return self._replay_parked(reaction, fill, hold)
        return self._read_blocker(state.runtime, reaction, fill, blocked, hold)

    def _read_blocker(
        self,
        runtime: GridRuntime,
        halted: Reaction,
        fill: LevelFill,
        level: int,
        hold: bool,
    ) -> Reaction:
        order = runtime.levels[level].order
        if order is None:
            return halted
        status = self._context.gateway.account_reads.order_status(order.client_order_id)
        bot_id = self._context.state.bot_id
        if status is OrderStatus.FILLED:
            self._parked.setdefault(order.client_order_id, []).append(fill)
            logger.warning(
                "Bot %s: the counter of %s found L%d holding %s, which the exchange has "
                "filled; parked until that fill is applied [blocked-counter]",
                bot_id,
                fill.client_order_id,
                level,
                order.client_order_id,
            )
            return Reaction(runtime)
        if status in _ENDED_UNFILLED and order.total_executed == 0:
            logger.warning(
                "Bot %s: the counter of %s found L%d holding %s, which the exchange has "
                "%s; freed the level [blocked-counter]",
                bot_id,
                fill.client_order_id,
                level,
                order.client_order_id,
                status.value,
            )
            freed = drop_order(runtime, order.client_order_id)
            return on_fill(freed, fill, self._context.terms.step_size, hold)
        return halted

    def _replay_parked(
        self, reaction: Reaction, fill: LevelFill, hold: bool
    ) -> Reaction:
        """The fills that waited for `fill`'s order, once its fill has settled the level."""
        waiting = self._parked.get(fill.client_order_id)
        if not waiting or reaction.runtime.level_of(fill.client_order_id) is not None:
            return reaction
        del self._parked[fill.client_order_id]
        for parked in waiting:
            if any(isinstance(action, Halt) for action in reaction.actions):
                break
            again = on_fill(
                reaction.runtime, parked, self._context.terms.step_size, hold
            )
            reaction = Reaction(
                again.runtime,
                (*reaction.actions, *again.actions),
                (*reaction.filled, *again.filled),
            )
        return reaction


def _blocked_level(reaction: Reaction) -> int | None:
    """The level whose order a counter found in its way, if the reaction halted on one."""
    for action in reaction.actions:
        if (
            isinstance(action, Halt)
            and action.reason is GridReason.DUPLICATE_LEVEL_ORDER
        ):
            return action.occupied_level
    return None
