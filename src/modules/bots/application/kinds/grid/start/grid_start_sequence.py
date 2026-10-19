"""`EPIC-029E` / `EPIC-039H` — the start of a Grid: the opening, then the ladder (ADR §3.1, §3.4).

  0. **Before anything is bought**, the ladder the opening will feed is sized and judged against
     the exchange's minimum by `grid_order_sizing`, the function the pre-start check judges
     with (`BUG-212`): an order under it refuses the start with nothing spent.
  1. **The opening** is the venue profile's (`IOpeningStrategy`): Spot buys the base the SELL
     levels will sell and sizes them net of the fee (`opening_spot.py`); a position venue
     opens its signed quantity (`opening_futures.py`). Either way the exchange's own record of
     it is counted before the ladder, and the sequence lays nothing when it is not there.
  1a. **The protective stop** (`EPIC-039L`, a position venue's `IExposureProtection`): it stands
     on the exchange, its id saved first, before the ladder is declared ready. One that cannot
     stand halts the bot, which closes its position; the ladder is not laid over a bare one.
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

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    fail_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stop_request import (
    stop_asked,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_protection import (
    IExposureProtection,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_order_sizing import (
    find_breach,
    find_cap_breach,
    smallest_order,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    BUDGET_QUOTE_ASSET,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStartSequence:
    """Takes the opening, lays the ladder, and reports RUNNING or why not."""

    def __init__(
        self,
        context: GridRunContext,
        opening: IOpeningStrategy,
        flags: IOrderFlags,
        protection: IExposureProtection,
    ) -> None:
        self._context = context
        self._opening = opening
        self._flags = flags
        self._protection = protection

    def run(self, plan: GridPlan) -> None:
        """Run the start for `plan`; the bot is STARTING."""
        state = self._context.state
        if not self._ladder_is_placeable(plan):
            return
        fresh = runtime_from_plan(plan, self._context.terms.step_size)
        # The rate this start read, kept for readers with no exchange (`BOT-194`).
        state.update(replace(fresh, maker_fee=self._context.terms.maker_fee))
        opened = self._opening.open(plan)
        if opened.ladder is None or not self._protection.protect(opened.ladder):
            return
        if self._place_ladder(opened.ladder):
            state.transition(BotLifecycleEvent.LADDER_READY)

    def _ladder_is_placeable(self, plan: GridPlan) -> bool:
        """Refuse the start, before any opening, when an order of the ladder it would lay is under
        the exchange's minimum (`BUG-212`) or, on a position venue, worth more than trading's
        per-order cap (`EPIC-039I`). The orders are sized by `grid_order_sizing`, the function the
        pre-start check judges with."""
        context = self._context
        terms = context.terms
        bot_id = context.state.bot_id
        breach = find_breach(context.params, plan, terms)
        over_cap = find_cap_breach(plan, terms)
        if breach is None and over_cap is not None:
            return self._refuse_unplaceable(
                f"the {over_cap.label} order is worth {over_cap.notional:.2f} "
                f"{BUDGET_QUOTE_ASSET}, above trading's cap of "
                f"{terms.max_notional_per_order} per order; use fewer grids or a smaller capital"
            )
        smallest = smallest_order(plan, terms)
        if breach is None:
            if smallest is not None:
                logger.info(
                    "Bot %s: ladder sized, smallest order %s %s x %s = %s (minimum %s) "
                    "[ladder-sizing]",
                    bot_id,
                    smallest.label,
                    smallest.quantity,
                    smallest.price,
                    smallest.notional,
                    terms.min_notional,
                )
            return True
        return self._refuse_unplaceable(
            breach.text(context.base_asset, BUDGET_QUOTE_ASSET)
        )

    def _refuse_unplaceable(self, detail: str) -> bool:
        context = self._context
        bot_id = context.state.bot_id
        logger.warning(
            "Bot %s: start refused before any order, %s [order-below-minimum]",
            bot_id,
            detail,
        )
        fail_with(
            context.state,
            OrderOutcome(OrderOutcomeKind.REFUSED, detail=detail),
            "the ladder cannot be placed",
        )
        return False

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
                maker_fee=earned.maker_fee,
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
        state.update(
            accepted(placed(state.runtime, as_accepted(action, outcome), oid), oid)
        )
        return True


def as_accepted(action: PlaceOrder, outcome: OrderOutcome) -> PlaceOrder:
    """`action` carrying the quantity the exchange accepted for it (`BUG-205`):
    the ladder saves, and the Orders panel shows, what rests, not what was asked."""
    if outcome.quantity is None or outcome.quantity == action.quantity:
        return action
    return replace(action, quantity=outcome.quantity)


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
