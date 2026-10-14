"""`EPIC-029E` — the stop of a Grid (ADR §3.1, §3.4, O3, D6).

The bot is STOPPING. In this order:

  1. **Register the budget again**, which re-derives the inventory from the
     exchange (D6): trading clears every budget on a disable or an Emergency
     Stop, and a tagged order without one is refused (`OWNER_BUDGET_MISSING`).
  2. **Cancel every order carrying the bot's tag.**
  3. **Keep the exposure, or close it** (the user's choice, O3; forced to *close* by a
     stop loss or take profit): by the venue profile's `IExposureCloser` — Spot sells the
     base in slices under the per-order cap (D21), a position venue sends reduce-only market
     orders for the bot's own derived position only (a position the owner opened by hand is
     left open and said so) and confirms it shrank by what it sold. A refused or failed slice
     halts the bot, naming the unsold remainder.
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

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_budget import (
    bot_owner_id,
)
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
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.stop.grid_stopping_wait import (
    WAITING,
    wait_in_stopping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.orders.bot_order_gateway import (
    OrderOutcomeKind,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_exposure_closer import (
    IExposureCloser,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.stop_progress import (
    StopProgress,
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
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.owner_budget_registration import (
    OwnerBudgetRefusal,
    OwnerBudgetRegistrationResult,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The cancel failures that end a stop at once, as a named fault or halt, instead
#: of waiting to retry: a request that raised, and an API key the exchange
#: rejects (`EPIC-035F`), which a retry cannot mend.
_ENDS_THE_STOP: frozenset[OrderOutcomeKind] = frozenset(
    {OrderOutcomeKind.FAULT, OrderOutcomeKind.KEY_REJECTED}
)


class GridStopSequence:
    """Cancels, keeps or sells, and confirms — or says why it waits."""

    def __init__(self, context: GridRunContext, closer: IExposureCloser) -> None:
        self._context = context
        self._closer = closer
        self._housekeeping = GridHousekeeping(context)

    def run(self, base: ExposureHandling, price: Decimal) -> StopProgress:
        """Run the stop; the bot is STOPPING. `price` references the exits."""
        registration = self._housekeeping.register()
        if not registration.registered:
            return self._budget_refused(registration)
        ended = self._cancel_tagged()
        if ended is not None:
            return ended
        if base is ExposureHandling.CLOSE_AT_MARKET:
            # A fill that landed while cancelling changed what the bot holds:
            # derive it again before closing it (ADR D6).
            registration = self._housekeeping.register()
            if not registration.registered:
                return self._budget_refused(registration)
            ended = self._closer.close(registration, price)
            if ended is not None:
                return ended
        return self._confirm()

    def wait_for_rate_limit(self, limited: ExchangeRateLimitedError) -> StopProgress:
        """A read of the stop met a rate limit: STOPPING waits out the pause."""
        self._context.gateway.note_rate_limit(limited.retry_after)
        wait_in_stopping(
            self._context,
            f"rate limited: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s",
        )
        return StopProgress.WAITING_ON_EXCHANGE

    def _budget_refused(
        self, registration: OwnerBudgetRegistrationResult
    ) -> StopProgress:
        wait_in_stopping(
            self._context, f"the budget was refused: {refusal_text(registration)}"
        )
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
        if failed.kind in _ENDS_THE_STOP:
            fail_with(self._context.state, failed, what)
            return StopProgress.ENDED
        wait_in_stopping(
            self._context,
            f"{what} refused: {failed.detail}; {report.remaining} order(s) still open",
        )
        if failed.kind is OrderOutcomeKind.SWITCH_OFF:
            return StopProgress.WAITING_FOR_TRADING
        return StopProgress.WAITING_ON_EXCHANGE

    def _confirm(self) -> StopProgress:
        state = self._context.state
        left = self._context.gateway.tagged_open_orders()
        if left:
            wait_in_stopping(
                self._context, f"{len(left)} order(s) carrying the tag are still open"
            )
            return StopProgress.WAITING_ON_EXCHANGE
        runtime = state.runtime
        if runtime.reason_detail.startswith(WAITING):
            # The wait is over: STOPPED shows why the bot stopped, not what
            # it once waited for.
            reason = runtime.reason or GridReason.USER_STOP
            state.update(runtime.with_reason(reason, reason.value))
        state.transition(BotLifecycleEvent.STOP_CONFIRMED)
        owner = bot_owner_id(state.bot_id)
        self._context.session.clear_owner_budget(owner)
        self._context.session.release_symbol(state.bot.definition.symbol, owner)
        return StopProgress.STOPPED
