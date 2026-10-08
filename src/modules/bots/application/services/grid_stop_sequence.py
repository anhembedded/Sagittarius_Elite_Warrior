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
from enum import Enum

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_budget import (
    bot_owner_id,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
    refusal_text,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.rate_limit_pause import (
    whole_seconds,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.market_slices import (
    base_slices,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The prefix of a reason detail while STOPPING waits; cleared on STOPPED.
_WAITING = "waiting:"


class StopProgress(str, Enum):
    """Where a run of the stop ended: what, if anything, it still waits for."""

    #: STOPPED: zero tagged orders were open.
    STOPPED = "stopped"
    #: STOPPING, on the exchange: a refused cancel, an order not yet gone, a
    #: budget or history read that did not answer. A later run can finish it.
    WAITING_ON_EXCHANGE = "waiting_on_exchange"
    #: STOPPING, on the order session: trading is off, so the switch-on event
    #: runs it again — a timer would only be refused.
    WAITING_FOR_TRADING = "waiting_for_trading"
    #: The bot left STOPPING (a fault, or a halted exit); a stop is asked anew.
    ENDED = "ended"


class GridStopSequence:
    """Cancels, keeps or sells, and confirms — or says why it waits."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        self._housekeeping = GridHousekeeping(context)

    def run(self, base: BaseHandling, price: Decimal) -> StopProgress:
        """Run the stop; the bot is STOPPING. `price` references the exits."""
        registration = self._housekeeping.register()
        if not registration.registered:
            return self._budget_refused(registration)
        ended = self._cancel_tagged()
        if ended is not None:
            return ended
        if base is BaseHandling.SELL_AT_MARKET:
            # A fill that landed while cancelling changed what the bot holds:
            # derive the inventory again before selling it (ADR D6).
            registration = self._housekeeping.register()
            if not registration.registered:
                return self._budget_refused(registration)
            ended = self._sell(registration, price)
            if ended is not None:
                return ended
        return self._confirm()

    def wait_for_rate_limit(self, limited: ExchangeRateLimitedError) -> StopProgress:
        """A read of the stop met a rate limit: STOPPING waits out the pause."""
        self._context.gateway.note_rate_limit(limited.retry_after)
        self._wait(
            f"rate limited: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s"
        )
        return StopProgress.WAITING_ON_EXCHANGE

    def _budget_refused(
        self, registration: OwnerBudgetRegistrationResult
    ) -> StopProgress:
        self._wait(f"the budget was refused: {refusal_text(registration)}")
        if registration.refusal is OwnerBudgetRefusal.TRADING_SWITCH_OFF:
            return StopProgress.WAITING_FOR_TRADING
        return StopProgress.WAITING_ON_EXCHANGE

    def _cancel_tagged(self) -> StopProgress | None:
        """`None` when every cancel was done; otherwise how the stop ended."""
        report = self._housekeeping.cancel_tagged()
        failed = report.failed
        if failed is None:
            return None
        what = f"cancel {report.client_order_id}"
        if failed.kind is OrderOutcomeKind.FAULT:
            fail_with(self._context.state, failed, what)
            return StopProgress.ENDED
        self._wait(
            f"{what} refused: {failed.detail}; {report.remaining} order(s) still open"
        )
        if failed.kind is OrderOutcomeKind.SWITCH_OFF:
            return StopProgress.WAITING_FOR_TRADING
        return StopProgress.WAITING_ON_EXCHANGE

    def _sell(
        self, registration: OwnerBudgetRegistrationResult, price: Decimal
    ) -> StopProgress | None:
        """`None` when the base is sold or kept as dust; otherwise how the stop ended."""
        inventory = (
            registration.inventory.quantity if registration.inventory else Decimal(0)
        )
        if inventory * price < self._context.terms.min_notional:
            logger.info(
                "Bot %s: %s %s kept as dust, worth less than the %s minimum",
                self._context.state.bot_id,
                inventory,
                self._context.base_asset,
                self._context.terms.min_notional,
            )
            return None
        slices = base_slices(
            inventory, price, self._context.cap, self._context.terms.market_step
        )
        remaining = sum(slices, Decimal(0))
        for index, piece in enumerate(slices, start=1):
            outcome = self._context.gateway.market_sell(piece, price)
            self._context.off_ladder.add(outcome.client_order_id)
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
                return StopProgress.WAITING_FOR_TRADING
            if outcome.kind is OrderOutcomeKind.RATE_LIMITED:
                # Nothing was sent: the next run derives what is left and sells it.
                self._wait(f"exit slice {index} not sent: {outcome.detail}")
                return StopProgress.WAITING_ON_EXCHANGE
            if not outcome.done:
                # A slice that raised may still have executed: say so rather
                # than count it unsold; the next stop or resume derives again.
                unsold = (
                    "possibly unsold (the request may have executed)"
                    if outcome.kind is OrderOutcomeKind.FAULT
                    else "unsold"
                )
                halt_with(
                    self._context.state,
                    GridReason.EXIT_SLICE_FAILED,
                    f"{remaining} {unsold} after slice {index}: {outcome.detail}",
                )
                return StopProgress.ENDED
            remaining -= piece
        return None

    def _confirm(self) -> StopProgress:
        state = self._context.state
        left = self._context.gateway.tagged_open_orders()
        if left:
            self._wait(f"{len(left)} order(s) carrying the tag are still open")
            return StopProgress.WAITING_ON_EXCHANGE
        runtime = state.runtime
        if runtime.reason_detail.startswith(_WAITING):
            # The wait is over: STOPPED shows why the bot stopped, not what
            # it once waited for.
            reason = runtime.reason or GridReason.USER_STOP
            state.update(runtime.with_reason(reason, reason.value))
        state.transition(BotLifecycleEvent.STOP_CONFIRMED)
        owner = bot_owner_id(state.bot_id)
        self._context.session.clear_owner_budget(owner)
        self._context.session.release_symbol(state.bot.definition.symbol, owner)
        return StopProgress.STOPPED

    def _wait(self, detail: str) -> None:
        state = self._context.state
        reason = state.runtime.reason or GridReason.USER_STOP
        state.update(state.runtime.with_reason(reason, f"{_WAITING} {detail}"))
        logger.info("Bot %s: STOPPING waits — %s", state.bot_id, detail)
