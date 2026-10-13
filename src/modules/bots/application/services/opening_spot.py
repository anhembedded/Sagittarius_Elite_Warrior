"""`EPIC-029E` — the Spot opening: buy the base the SELL levels will sell (ADR §3.1, D21).

0. **Earlier runs** (`BUG-196`): what the bot's earlier runs left on the account is read and
   recorded on the run, never traded and never a reason to refuse.
1. **The opening buy** goes out in slices at or below the per-order cap, each waiting its
   turn (D21): ⌈quote / cap⌉ market BUYs.
2. **Counted from the exchange**, not only from the stream: the market buy's placement
   response lists its trades (`BOT-173`), and between the buy and the ladder the bot has
   trading register its budget again, which derives the inventory from the exchange's own
   record of the bot's orders (D6). The ladder is laid only when that inventory covers the
   SELLs; a buy the record does not show yet halts the start with `start_refused`, naming
   what was counted (`BUG-194`). The stream's later report of the same fill is not counted
   again (`OwnerBook.apply_fill`).
3. **The ladder is sized net of the opening's fee**, which Spot takes from the base bought
   (`sells_net_of_opening_fee`).
"""

from __future__ import annotations

import logging
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_request import (
    stop_asked,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
    OpeningResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
    sells_net_of_opening_fee,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    quote_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class SpotOpening(IOpeningStrategy):
    """Buys the opening base, has it counted, and sizes the SELLs net of its fee."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)
        self._earlier_runs = GridEarlierRuns(context)

    def open(self, plan: GridPlan) -> OpeningResult:
        terms = self._context.terms
        self._earlier_runs.record()
        ladder = sells_net_of_opening_fee(plan, terms.taker_fee, terms.step_size)
        if self._buy_opening(plan) and self._count_opening(ladder):
            return OpeningResult(ladder)
        return OpeningResult(None)

    def _buy_opening(self, plan: GridPlan) -> bool:
        quote = plan.opening_buy_quantity * plan.last_price
        for index, piece in enumerate(quote_slices(quote, self._context.cap), start=1):
            if stop_asked(self._context):
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
