"""`EPIC-029E` — the start of a Grid: the opening buy, then the ladder (ADR §3.1, §3.4).

  1. **The opening buy** goes out in slices at or below the per-order cap, each
     waiting its turn (D21): ⌈quote / cap⌉ market BUYs.
  2. **The ladder**, outward from the last price; the level nearest the price
     stays EMPTY. Each SELL is sized net of the opening's fee, which Spot
     takes from the base bought (`sells_net_of_opening_fee`).
  3. **RUNNING** (`ladder_ready`) only once every other level rests.

A refusal stops the sequence. After anything was bought or placed, the bot
halts with the reason (`start_refused`), its inventory still accounted, so
the user can resume (re-plan) or stop; the executor then takes what was
placed off the exchange, as on every halt (`GridExecutor._park`). Trading
off is `switch_off`; a request that raised is `fault` (`grid_order_failure`).

Start's preconditions (venue, verdicts, lease, budget) are the start use case's,
checked before the bot ever reached STARTING.

@par Known limit
A SELL level is placed against the base the opening bought, and trading counts
that base only when the fill event arrives on the user data stream. The pacer's
spacing separates the last opening slice from the first SELL; a stream slower
than that refuses the SELL (`owner_budget_sell_exceeds_inventory`) and the bot
halts with `start_refused`, from which a resume re-plans with the inventory
then derived. `EPIC-029H` measures the stream's latency on Testnet.
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    runtime_from_plan,
    sells_net_of_opening_fee,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    PlaceOrder,
    accepted,
    placed,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    quote_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStartSequence:
    """Buys the opening, lays the ladder, and reports RUNNING or why not."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def run(self, plan: GridPlan) -> None:
        """Run the start for `plan`; the bot is STARTING."""
        state = self._context.state
        terms = self._context.terms
        state.update(runtime_from_plan(plan, terms.step_size))
        ladder = sells_net_of_opening_fee(plan, terms.taker_fee, terms.step_size)
        if self._buy_opening(plan) and self._place_ladder(ladder):
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
            )
        )
        if self._place_ladder(plan):
            state.transition(BotLifecycleEvent.LADDER_READY)

    def _buy_opening(self, plan: GridPlan) -> bool:
        quote = plan.opening_buy_quantity * plan.last_price
        for index, piece in enumerate(quote_slices(quote, self._context.cap), start=1):
            outcome = self._context.gateway.market_buy(piece, plan.last_price)
            self._context.off_ladder.add(outcome.client_order_id)
            logger.info(
                "Bot %s: opening buy slice %d of %s USDT -> %s %s",
                self._context.state.bot_id,
                index,
                piece,
                outcome.kind.value,
                outcome.client_order_id or outcome.detail,
            )
            if not outcome.done:
                fail_with(self._context.state, outcome, f"opening buy slice {index}")
                return False
        return True

    def _place_ladder(self, plan: GridPlan) -> bool:
        return all(self._place(action) for action in ladder_orders(plan))

    def _place(self, action: PlaceOrder) -> bool:
        state = self._context.state
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
