"""`EPIC-029E` — lays a Grid's orders: what a reaction asks the executor to place.

Split from `GridExecutor` (`EPIC-035B`, `architecture-rule.md` §5.4) because the
placing is one abstraction level below the actor's queue and its facts: the
executor decides what happened, this sends the orders that follows from it,
one at a time and stopping at the first that does not go through.

A RUNNING ladder whose order the exchange refuses for the symbol's status
(`EPIC-035E`) pauses instead of halting: the order it could not place and every
order still owed after it are **held** (as a pause holds them), so the resume
places them and no counter order is lost. Its ladder keeps resting.

A RUNNING ladder whose order the exchange refuses for its own numbers
(`OrderOutcomeKind.ORDER_INVALID`, `EPIC-035T`) leaves that rung EMPTY, names it
and goes on; a rung refused twice within a minute halts (`rejected_counter`).
"""

from __future__ import annotations

import logging

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_sequence import (
    log_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_rejection import (
    rejected_counter,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    GridAction,
    Halt,
    PlaceOrder,
    accepted,
    hold_order,
    placed,
    release_held,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridLadderPlacer:
    """Places the orders a reaction owes, on the bot's worker."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def release_held(self) -> None:
        """Place what a pause held back."""
        state = self._context.state
        reaction = release_held(state.runtime)
        state.update(reaction.runtime)
        self.act(reaction.actions)

    def act(self, actions: tuple[GridAction, ...]) -> None:
        for index, action in enumerate(actions):
            if isinstance(action, Halt):
                halt_with(self._context.state, action.reason, action.detail)
                return
            if not self._place(action, actions[index + 1 :]):
                return

    def _place(self, action: PlaceOrder, later: tuple[GridAction, ...]) -> bool:
        state = self._context.state
        if state.runtime.levels[action.level_index].state is not LevelState.EMPTY:
            halt_with(
                state,
                GridReason.DUPLICATE_LEVEL_ORDER,
                f"L{action.level_index} already holds an order; nothing was sent",
            )
            return False
        outcome = self._context.gateway.place_limit(
            action.side, action.price, action.quantity
        )
        log_order(state.bot_id, action, outcome.client_order_id or outcome.detail)
        what = f"L{action.level_index} {action.side.value}"
        if (
            outcome.kind is OrderOutcomeKind.SYMBOL_NOT_TRADING
            and state.state is BotLifecycleState.RUNNING
        ):
            self._pause_for_status(outcome, what, (action, *later))
            return False
        if (
            outcome.kind is OrderOutcomeKind.ORDER_INVALID
            and state.state is BotLifecycleState.RUNNING
        ):
            return self._leave_rung_empty(action, f"{what}: {outcome.detail}")
        if not outcome.done:
            fail_with(state, outcome, what)
            return False
        oid = outcome.client_order_id
        state.update(accepted(placed(state.runtime, action, oid), oid))
        return True

    def _leave_rung_empty(self, action: PlaceOrder, detail: str) -> bool:
        """Keep the ladder running without `action`'s rung; `False` when the rung
        was refused twice within a minute and the bot halted instead."""
        state = self._context.state
        reaction = rejected_counter(state.runtime, action, state.now(), detail)
        state.update(reaction.runtime)
        logger.warning(
            "Bot %s: %s was refused for its own numbers; L%d stays empty [counter-rejected]",
            state.bot_id,
            detail,
            action.level_index,
        )
        for halt in reaction.actions:
            if isinstance(halt, Halt):
                halt_with(state, halt.reason, halt.detail)
                return False
        return True

    def _pause_for_status(
        self, outcome: OrderOutcome, what: str, owed: tuple[GridAction, ...]
    ) -> None:
        """Hold every order still owed and pause, naming the status."""
        state = self._context.state
        runtime = state.runtime
        for pending in owed:
            if not isinstance(pending, PlaceOrder):
                continue
            reaction = hold_order(runtime, pending)
            runtime = reaction.runtime
            for halt in reaction.actions:
                if isinstance(halt, Halt):
                    state.update(runtime)
                    halt_with(state, halt.reason, halt.detail)
                    return
        state.update(runtime)
        state.transition(
            BotLifecycleEvent.PAUSE,
            GridReason.SYMBOL_NOT_TRADING,
            f"{what}: {outcome.detail}",
        )
