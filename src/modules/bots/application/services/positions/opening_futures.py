"""`EPIC-039H` — the position venue's opening: the plan's signed quantity at market, counted from the exchange.

  0. **The start's own checks** (`FuturesStartChecks`): settings made the bot's, the plan's
     liquidation risk judged. Nothing is sent before they pass.
  1. **The opening** is the plan's `opening_quantity` (LONG: a market BUY of the SELL levels'
     quantity; SHORT: a market SELL of the BUY levels'; NEUTRAL opens nothing: no slice is sent), cut under the
     per-order cap like Spot's, but in base quantity: there is no quote-sized order on a position
     venue, and no base fee to net — a position's fee is paid in the quote asset.
  2. **Counted from the exchange**: trading registers the budget again, which derives the position
     from the exchange's record of the bot's fills and checks it against `positionRisk`. The ladder
     is laid only when the position covers the reduce-only orders (LONG's SELLs, SHORT's BUYs), and **never over a registration
     that returned a divergence** (the exchange's position differs from the bot's own fills: the
     start is refused, nothing is laid, and the guard — `EPIC-039F` — has the say once running).

The direction is data of the plan (`GridPlan.opening_quantity` is signed): this class reads the
sign and nothing else, so the three directions share one path.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.venue.futures_start_checks import (
    FuturesStartChecks,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_opening_strategy import (
    IOpeningStrategy,
    OpeningResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_ladder import (
    ladder_orders,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_plan import GridPlan
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.position_order_sizing import (
    first_breach,
)
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
        breach = first_breach(plan, self._context.terms)
        if breach is not None:
            logger.warning(
                "Bot %s: an order of the ladder breaks the exchange's filters: %s "
                "[order-breach]",
                self._context.state.bot_id,
                breach.describe(self._context.terms),
            )
            return self._refuse(
                breach.describe(self._context.terms),
                "an order of the ladder would be refused by the exchange",
            )
        refusal = self._checks.refusal(plan)
        if refusal is not None:
            return self._refuse(refusal, "the start was refused")
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
        side = OrderSide.BUY if plan.opening_quantity > 0 else OrderSide.SELL
        slices = base_slices(
            abs(plan.opening_quantity),
            plan.last_price,
            context.cap,
            context.terms.market_step,
        )
        for index, piece in enumerate(slices, start=1):
            if stop_asked(context):
                return False
            outcome = context.gateway.market_base(side, piece, plan.last_price)
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
        exits_side = OrderSide.SELL if plan.opening_quantity > 0 else OrderSide.BUY
        # A NEUTRAL plan opens nothing and lays nothing reduce-only: no position is owed.
        exiting = sum(
            (
                a.quantity
                for a in ladder_orders(plan)
                if a.side is exits_side and plan.opening_quantity != 0
            ),
            Decimal(0),
        )
        if held * (1 if plan.opening_quantity > 0 else -1) < exiting:
            self._refuse(
                f"the exchange's record of the opening holds {held} {self._context.base_asset}, "
                f"the ladder's reduce-only {exits_side.value}s need {exiting}; nothing was laid",
                "the opening is not in the exchange's record",
            )
            return False
        logger.info(
            "Bot %s: opening counted from the exchange's record: a position of %s, the "
            "ladder's reduce-only %ss add up to %s [position-opened]",
            state.bot_id,
            held,
            exits_side.value,
            exiting,
        )
        return True
