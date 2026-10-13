"""`EPIC-029E` / `EPIC-039H` — the start of a Grid: the opening, then the ladder (ADR §3.1, §3.4).

  1. **The opening** is the venue profile's (`IOpeningStrategy`): Spot buys the base the SELL
     levels will sell and sizes them net of the fee (`opening_spot.py`); a position venue
     opens its signed quantity (`opening_futures.py`). Either way the exchange's own record of
     it is counted before the ladder, and the sequence lays nothing when it is not there.
  2. **The ladder**, outward from the last price; the level nearest the price stays EMPTY.
     Each order carries the venue's flags (`IOrderFlags`: reduce-only counters on a position
     venue).
  3. **RUNNING** (`ladder_ready`) only once every other level rests.

A refusal stops the sequence. After anything was bought or placed, the bot
halts with the reason (`start_refused`), its inventory still accounted, so
the user can resume (re-plan) or stop; the executor then takes what was
placed off the exchange, as on every halt (`GridTaskGuard._park`). Trading
off is `switch_off`; a request that raised is `fault` (`grid_order_failure`).

Start's preconditions (venue, verdicts, lease, budget) are the start use case's,
checked before the bot ever reached STARTING.
"""

from __future__ import annotations

import logging
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_request import (
    stop_asked,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_order_flags import (
    IOrderFlags,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    runtime_from_plan,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    PlaceOrder,
    accepted,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStartSequence:
    """Takes the opening, lays the ladder, and reports RUNNING or why not."""

    def __init__(
        self,
        context: GridRunContext,
        opening: IOpeningStrategy,
        flags: IOrderFlags,
    ) -> None:
        self._context = context
        self._opening = opening
        self._flags = flags

    def run(self, plan: GridPlan) -> None:
        """Run the start for `plan`; the bot is STARTING."""
        state = self._context.state
        state.update(runtime_from_plan(plan, self._context.terms.step_size))
        opened = self._opening.open(plan)
        if opened.ladder is not None and self._place_ladder(opened.ladder):
            state.transition(BotLifecycleEvent.LADDER_READY)

    def place_ladder(self, plan: GridPlan, inventory: OwnerInventory) -> None:
        """Lay `plan`'s ladder without an opening buy (a confirmed resume, D13).

        The run goes on: the inventory is the one trading derived, and what
        the run has earned so far is kept."""
        state = self._context.state
        earned = state.runtime
        fresh = runtime_from_plan(plan, self._context.terms.step_size)
        state.update(
            replace(
                fresh,
                inventory=inventory.quantity,
                cost=inventory.cost,
                realised_profit=earned.realised_profit,
                completed_cycles=earned.completed_cycles,
                realised_total=earned.realised_total,
                start_price=earned.start_price or fresh.start_price,
                mark_price=earned.mark_price,
                mark_price_at=earned.mark_price_at,
                unpriced_fees=earned.unpriced_fees,
                earlier_runs_base=earned.earlier_runs_base,
                earlier_runs_cost=earned.earlier_runs_cost,
            )
        )
        if self._place_ladder(plan):
            state.transition(BotLifecycleEvent.LADDER_READY)

    def _place_ladder(self, plan: GridPlan) -> bool:
        return all(self._place(action) for action in ladder_orders(plan))

    def _place(self, action: PlaceOrder) -> bool:
        if stop_asked(self._context):
            return False
        state = self._context.state
        outcome = self._context.gateway.place_limit(
            action.side,
            action.price,
            action.quantity,
            reduce_only=self._flags.reduce_only(action.side),
        )
        log_order(state.bot_id, action, outcome.client_order_id or outcome.detail)
        if not outcome.done:
            fail_with(state, outcome, f"L{action.level_index} {action.side.value}")
            return False
        oid = outcome.client_order_id
        state.update(accepted(placed(state.runtime, action, oid), oid))
        return True


def log_order(bot_id: str, action: PlaceOrder, result: str) -> None:
    logger.info(
        "Bot %s: L%d %s %s @ %s -> %s",
        bot_id,
        action.level_index,
        action.side.value,
        action.quantity,
        action.price,
        result,
    )
