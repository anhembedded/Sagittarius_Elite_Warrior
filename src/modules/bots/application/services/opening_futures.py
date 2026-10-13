"""`EPIC-039H` — the position venue's opening: the plan's signed quantity at market, counted from the exchange.

  0. **The start's own checks** (`FuturesStartChecks`): settings made the bot's, the plan's
     liquidation risk judged. Nothing is sent before they pass.
  1. **The opening** is the plan's `opening_quantity` (LONG: a market BUY of the SELL levels'
     quantity), cut under the per-order cap like Spot's, but in base quantity: there is no
     quote-sized order on a position venue, and no base fee to net — a position's fee is paid in the
     quote asset.
  2. **Counted from the exchange**: trading registers the budget again, which derives the position
     from the exchange's record of the bot's fills and checks it against `positionRisk`. The ladder
     is laid only when the position covers the reduce-only SELLs, and **never over a registration
     that returned a divergence** (the exchange's position differs from the bot's own fills: the
     start is refused, nothing is laid, and the guard — `EPIC-039F` — has the say once running).

Only LONG opens here (`EPIC-039I` adds the rest); a plan opening on the other side is refused.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.futures_start_checks import (
    FuturesStartChecks,
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
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order_side import OrderSide
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class PositionOpening(IOpeningStrategy):
    """Opens the plan's position at market, has it counted, and lays the ladder over it."""

    def __init__(self, context: GridRunContext, checks: FuturesStartChecks) -> None:
        self._context = context
        self._checks = checks
        self._housekeeping = GridHousekeeping(context)

    def open(self, plan: GridPlan) -> OpeningResult:
        refusal = self._checks.refusal(plan)
        if refusal is not None:
            return self._refuse(refusal, "the start was refused")
        if plan.opening_quantity < 0:
            return self._refuse(
                "this bot would open a short position, which is not available yet",
                "the opening is not available",
            )
        if self._open_position(plan) and self._count_opening(plan):
            return OpeningResult(plan)
        return OpeningResult(None)

    def _refuse(self, detail: str, what: str) -> OpeningResult:
        fail_with(
            self._context.state,
            OrderOutcome(OrderOutcomeKind.REFUSED, detail=detail),
            what,
        )
        return OpeningResult(None)

    def _open_position(self, plan: GridPlan) -> bool:
        context = self._context
        slices = base_slices(
            plan.opening_quantity,
            plan.last_price,
            context.cap,
            context.terms.market_step,
        )
        for index, piece in enumerate(slices, start=1):
            if stop_asked(context):
                return False
            outcome = context.gateway.market_buy_base(piece, plan.last_price)
            context.off_ladder.add(outcome.client_order_id)
            logger.info(
                "Bot %s: opening slice %d of %s -> %s %s",
                context.state.bot_id,
                index,
                piece,
                outcome.kind.value,
                outcome.client_order_id or outcome.detail,
            )
            if not outcome.done:
                fail_with(context.state, outcome, f"opening slice {index}")
                return False
        return True

    def _count_opening(self, plan: GridPlan) -> bool:
        """Have trading count the opening from the exchange's record, and say whether the
        reduce-only SELLs of `plan` are covered by the position it derived."""
        state = self._context.state
        registration = self._housekeeping.register()
        if not registration.registered or registration.position is None:
            kind = (
                OrderOutcomeKind.SWITCH_OFF
                if registration.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF
                else OrderOutcomeKind.REFUSED
            )
            fail_with(
                state,
                OrderOutcome(kind, detail=refusal_text(registration)),
                "the opening could not be counted from the exchange",
            )
            return False
        divergence = registration.divergence
        if divergence is not None:
            self._refuse(
                f"the exchange holds {divergence.exchange} and the bot's own fills add up to "
                f"{divergence.derived}; nothing was laid",
                "the opening does not match the exchange",
            )
            return False
        held = registration.position.quantity
        selling = sum(
            (a.quantity for a in ladder_orders(plan) if a.side is OrderSide.SELL),
            Decimal(0),
        )
        if held < selling:
            self._refuse(
                f"the exchange's record of the opening holds {held} {self._context.base_asset}, "
                f"the ladder's SELLs need {selling}; nothing was laid",
                "the opening is not in the exchange's record",
            )
            return False
        logger.info(
            "Bot %s: opening counted from the exchange's record: a position of %s, the "
            "ladder sells %s [position-opened]",
            state.bot_id,
            held,
            selling,
        )
        return True
