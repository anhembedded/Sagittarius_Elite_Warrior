"""`EPIC-029E` — lays a Grid's orders: what a reaction asks the executor to place.

Split from `GridExecutor` (`EPIC-035B`, `architecture-rule.md` §5.4) because the
placing is one abstraction level below the actor's queue and its facts: the
executor decides what happened, this sends the orders that follows from it,
one at a time and stopping at the first that does not go through.
"""

from __future__ import annotations

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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_level_fsm_matrix import (
    LevelState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    GridAction,
    Halt,
    PlaceOrder,
    accepted,
    placed,
    release_held,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)


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
        for action in actions:
            if isinstance(action, Halt):
                halt_with(self._context.state, action.reason, action.detail)
                return
            if not self._place(action):
                return

    def _place(self, action: PlaceOrder) -> bool:
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
        if not outcome.done:
            fail_with(state, outcome, f"L{action.level_index} {action.side.value}")
            return False
        oid = outcome.client_order_id
        state.update(accepted(placed(state.runtime, action, oid), oid))
        return True
