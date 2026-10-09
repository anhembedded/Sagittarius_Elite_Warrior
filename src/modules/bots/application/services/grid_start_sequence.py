"""`EPIC-029E` — the start of a Grid: the opening buy, then the ladder (ADR §3.1, §3.4).

  0. **Earlier runs** (`BUG-196`): what the bot's earlier runs left on the account
     is read and recorded on the run, never traded and never a reason to refuse.
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

@par The opening buy is counted from the exchange, not from the stream
A SELL level is placed against the base the opening bought, and trading's owner
book learns that base from the user data stream. A stream that is down, or later
than the first SELL, left the inventory at zero and refused the SELL
(`owner_budget_sell_exceeds_inventory`) with the buy already paid for
(`BUG-194`). So between the opening buy and the ladder the bot has trading
register its budget again, which derives the inventory from the exchange's own
record of the bot's orders (D6), and lays the ladder only when that inventory
covers the SELLs. A buy the record does not show yet halts the start with
`start_refused`, naming what was counted; the stream's later report of the same
fill is not counted again (`OwnerBook.apply_fill`).
"""

from __future__ import annotations

import logging
from dataclasses import replace
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_earlier_runs import (
    GridEarlierRuns,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget import (
    OwnerInventory,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStartSequence:
    """Buys the opening, lays the ladder, and reports RUNNING or why not."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)
        self._earlier_runs = GridEarlierRuns(context)

    def run(self, plan: GridPlan) -> None:
        """Run the start for `plan`; the bot is STARTING."""
        state = self._context.state
        terms = self._context.terms
        state.update(runtime_from_plan(plan, terms.step_size))
        self._earlier_runs.record()
        ladder = sells_net_of_opening_fee(plan, terms.taker_fee, terms.step_size)
        if (
            self._buy_opening(plan)
            and self._count_opening(ladder)
            and self._place_ladder(ladder)
        ):
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

    def _buy_opening(self, plan: GridPlan) -> bool:
        quote = plan.opening_buy_quantity * plan.last_price
        for index, piece in enumerate(quote_slices(quote, self._context.cap), start=1):
            if self._stop_asked():
                return False
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

    def _count_opening(self, ladder: GridPlan) -> bool:
        """Have trading count the opening buy from the exchange's record, and
        say whether the SELLs of `ladder` are now covered by what it counted."""
        state = self._context.state
        registration = self._housekeeping.register()
        if not registration.registered or registration.inventory is None:
            kind = (
                OrderOutcomeKind.SWITCH_OFF
                if registration.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF
                else OrderOutcomeKind.REFUSED
            )
            fail_with(
                state,
                OrderOutcome(kind, detail=refusal_text(registration)),
                "the opening buy could not be counted from the exchange",
            )
            return False
        held = registration.inventory.quantity
        selling = sum(
            (a.quantity for a in ladder_orders(ladder) if a.side is OrderSide.SELL),
            Decimal(0),
        )
        base = self._context.base_asset
        if held < selling:
            fail_with(
                state,
                OrderOutcome(
                    OrderOutcomeKind.REFUSED,
                    detail=(
                        f"the exchange's record of the opening buy holds {held} {base}, "
                        f"the ladder's SELLs need {selling}; nothing was laid"
                    ),
                ),
                "the opening buy is not in the exchange's record",
            )
            return False
        logger.info(
            "Bot %s: opening buy counted from the exchange's record: %s %s held, "
            "the ladder sells %s",
            state.bot_id,
            held,
            base,
            selling,
        )
        return True

    def _place_ladder(self, plan: GridPlan) -> bool:
        return all(self._place(action) for action in ladder_orders(plan))

    def _stop_asked(self) -> bool:
        """The user pressed Stop while this start ran: it lays nothing more and
        leaves the bot STARTING for the Stop queued behind it to end
        (`EPIC-035V`, L9)."""
        if not self._context.stop_requested.is_set():
            return False
        logger.info(
            "Bot %s: Stop asked; the start lays no more orders",
            self._context.state.bot_id,
        )
        return True

    def _place(self, action: PlaceOrder) -> bool:
        if self._stop_asked():
            return False
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
