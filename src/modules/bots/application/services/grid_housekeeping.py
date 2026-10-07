"""`EPIC-029E` — the two steps every recovery of a Grid begins with (ADR D6, D13, §3.3).

· **`register`** asks trading for the bot's budget again, which re-derives
  its inventory from the exchange. Trading clears every budget on a disable
  or an Emergency Stop, and a tagged order without one is refused, so the
  bot does this before any order in any state: a stop, a resume from HALTED,
  a reconciliation, ERROR → `stop`.
· **`cancel_tagged`** cancels every open order carrying the bot's tag, and
  empties the levels that held them. It answers whether every cancel was
  done; on the first that was not, it stops and names it.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcome,
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    grid_budget,
    grid_registration,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    drop_order,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.order import Order
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")


@dataclass(frozen=True, slots=True)
class CancelReport:
    """Every tagged order cancelled, or the first cancel that was not."""

    failed: OrderOutcome | None = None
    client_order_id: str = ""

    @property
    def done(self) -> bool:
        return self.failed is None


class GridHousekeeping:
    """Re-registers a Grid's budget and clears its tagged orders."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def register(self) -> OwnerBudgetRegistrationResult:
        bot = self._context.state.bot
        run_started_at = bot.lifecycle.run_started_at
        if run_started_at is None:
            raise ValueError(f"Bot {bot.bot_id} has no run to register a budget for")
        return self._context.session.register_owner_budget(
            grid_registration(
                bot.bot_id.value,
                bot.definition.symbol,
                run_started_at,
                grid_budget(self._context.params, self._context.caps),
            )
        )

    def cancel_tagged(self) -> CancelReport:
        state = self._context.state
        for order in self._context.gateway.tagged_open_orders():
            outcome = self._context.gateway.cancel(order.client_order_id)
            logger.info(
                "Bot %s: cancel %s -> %s %s",
                state.bot_id,
                order.client_order_id,
                outcome.kind.value,
                outcome.detail,
            )
            if not outcome.done and not self._ended_meanwhile(outcome, order):
                return CancelReport(outcome, order.client_order_id)
            state.update(drop_order(state.runtime, order.client_order_id))
            self._context.off_ladder.add(order.client_order_id)
        return CancelReport()

    def _ended_meanwhile(self, outcome: OrderOutcome, order: Order) -> bool:
        """A cancel that raised for an order no longer open: it filled or
        ended between the read and the cancel (Binance answers -2011, "Unknown
        order sent."), so there is nothing left to cancel. Its fill, if any,
        arrives as an event and is booked as the bot's inventory."""
        if outcome.kind is not OrderOutcomeKind.FAULT:
            return False
        still_open = {
            o.client_order_id for o in self._context.gateway.tagged_open_orders()
        }
        if order.client_order_id in still_open:
            return False
        logger.info(
            "Bot %s: %s ended before its cancel (%s)",
            self._context.state.bot_id,
            order.client_order_id,
            outcome.detail,
        )
        return True


def refusal_text(registration: OwnerBudgetRegistrationResult) -> str:
    refusal = registration.refusal
    if refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF:
        return "the order session is not open"
    return refusal.value if refusal else ""
