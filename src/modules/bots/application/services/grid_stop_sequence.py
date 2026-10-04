"""`EPIC-029E` — the stop of a Grid (ADR §3.1, §3.4, O3, D6).

The bot is STOPPING. In this order:

  1. **Register the budget again**, which re-derives the inventory from the
     exchange (D6): trading clears every budget on a disable or an Emergency
     Stop, and a tagged order without one is refused (`OWNER_BUDGET_MISSING`).
  2. **Cancel every order carrying the bot's tag.**
  3. **Keep the base, or sell it** (the user's choice, O3; forced to *sell* by a
     stop loss or take profit): in slices at or below the per-order cap, each
     waiting its turn (D21). A refused or failed slice halts the bot, naming the
     unsold remainder.
  4. **Read the open orders again.** Only zero orders carrying the tag raise
     `stop_confirmed` (STOPPED); then the bot clears its budget and releases the
     lease. Anything else leaves it STOPPING — it is never reported stopped
     early.

While trading is off the registration and the cancels are refused, so the bot
waits in STOPPING, its reason saying so, and runs this again when trading is
enabled (the switch handler). The same sequence is ERROR's exit.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
    grid_budget,
    grid_registration,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fail_with,
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_reactions import (
    drop_order,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")


class GridStopSequence:
    """Cancels, keeps or sells, and confirms — or says why it waits."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context

    def run(self, base: BaseHandling, price: Decimal) -> None:
        """Run the stop; the bot is STOPPING. `price` references the exits."""
        registration = self.register()
        if not registration.registered:
            self._wait(f"the budget was refused: {_refusal_text(registration)}")
            return
        if not self._cancel_tagged():
            return
        if base is BaseHandling.SELL_AT_MARKET and not self._sell(registration, price):
            return
        self._confirm()

    def register(self) -> OwnerBudgetRegistrationResult:
        """Ask trading for the bot's budget again, re-deriving its inventory."""
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

    def _cancel_tagged(self) -> bool:
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
            if outcome.kind is OrderOutcomeKind.FAULT:
                fail_with(state, outcome, f"cancel {order.client_order_id}")
                return False
            if not outcome.done:
                self._wait(f"cancel {order.client_order_id} refused: {outcome.detail}")
                return False
            state.update(drop_order(state.runtime, order.client_order_id))
        return True

    def _sell(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> bool:
        inventory = (
            registration.inventory.quantity if registration.inventory else Decimal(0)
        )
        slices = base_slices(
            inventory, price, self._context.cap, self._context.terms.step_size
        )
        remaining = sum(slices, Decimal(0))
        for index, piece in enumerate(slices, start=1):
            outcome = self._context.gateway.market_sell(piece, price)
            logger.info(
                "Bot %s: exit slice %d of %s -> %s %s",
                self._context.state.bot_id,
                index,
                piece,
                outcome.kind.value,
                outcome.client_order_id or outcome.detail,
            )
            if outcome.kind is OrderOutcomeKind.SWITCH_OFF:
                self._wait(f"exit slice {index} refused: trading is off")
                return False
            if not outcome.done:
                halt_with(
                    self._context.state,
                    GridReason.EXIT_SLICE_FAILED,
                    f"{remaining} unsold after slice {index}: {outcome.detail}",
                )
                return False
            remaining -= piece
        return True

    def _confirm(self) -> None:
        state = self._context.state
        left = self._context.gateway.tagged_open_orders()
        if left:
            self._wait(f"{len(left)} order(s) carrying the tag are still open")
            return
        state.transition(BotLifecycleEvent.STOP_CONFIRMED)
        owner = bot_owner_id(state.bot_id)
        self._context.session.clear_owner_budget(owner)
        self._context.session.release_symbol(state.bot.definition.symbol, owner)

    def _wait(self, detail: str) -> None:
        state = self._context.state
        reason = state.runtime.reason or GridReason.USER_STOP
        state.update(state.runtime.with_reason(reason, f"waiting: {detail}"))
        logger.info("Bot %s: STOPPING waits — %s", state.bot_id, detail)


def _refusal_text(registration: OwnerBudgetRegistrationResult) -> str:
    refusal = registration.refusal
    if refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF:
        return "trading is off"
    return refusal.value if refusal else ""
