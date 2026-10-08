"""`EPIC-029E` — what wraps every task a Grid's worker runs (ADR D9, D13).

Two guarantees, both PR 325 review findings:

  · **No failure leaves a bot without a reason.** The gateway names every
    order outcome; a step outside an order that raises (a price, terms or
    history read, a value the ladder refused) becomes `fault` (ERROR) with
    the step and the error, logged with its traceback (`code/errors.md` §3:
    converted at the seam where it becomes a lifecycle fact).
  · **A bot that stops placing takes its ladder off the exchange.** A task
    that leaves the bot HALTED or ERROR, other than a switch-off, cancels
    every order carrying its tag, so nothing keeps trading while nobody
    places its counters. A switch-off is the exception: cancels are refused
    then, and the orders rest by design (D13). What could not be cancelled
    is named beside the reason, never replacing it.

"Parked" is inferred from the fact that orders may rest, never from a state
change alone (`EPIC-035C`, H4): a confirmed resume begins in HALTED, lays part
of the ladder and is refused part-way, ending HALTED again, and its placed
orders must not keep trading. So the guard parks when the bot **fell into**
HALTED or ERROR during the task, or when the task **sent orders** and ended
there. A bot already parked whose task sent nothing is left alone, so a parked
bot does not read the book again on every tick.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_housekeeping import (
    GridHousekeeping,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    fault_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_rate_limit_pause import (
    GridRateLimitPause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The states a bot takes its ladder off the exchange on entering, unless
#: trading switched off.
_PARKED: frozenset[BotLifecycleState] = frozenset(
    {BotLifecycleState.HALTED, BotLifecycleState.ERROR}
)

#: Halts after which the ladder stays where it is because a cancel would be
#: refused: a closed order session (D13; a start it cut short owes the cancel
#: instead, `BUG-190`) and a rate-limit pause (`EPIC-035D`, whose resume cancels
#: every tagged order first).
_NOT_PARKED: frozenset[GridReason] = frozenset(
    {
        GridReason.SWITCH_OFF,
        GridReason.START_CUT_BY_SWITCH_OFF,
        GridReason.RATE_LIMITED,
    }
)


class GridTaskGuard:
    """Runs one worker task, then parks the ladder if the task stopped placing."""

    def __init__(
        self,
        context: GridRunContext,
        housekeeping: GridHousekeeping,
        pause: GridRateLimitPause,
    ) -> None:
        self._context = context
        self._housekeeping = housekeeping
        self._pause = pause

    def run(self, what: str, task: Callable[[], None]) -> None:
        """Run `task`, named `what` in any fault it becomes."""
        state = self._context.state
        before = state.state
        sent_before = self._context.gateway.submissions
        self._context.gateway.take_rate_limit()  # a pause from an earlier task is spent
        try:
            task()
        except ExchangeRateLimitedError as limited:
            # `EPIC-035D` — a pause the exchange named, not a failure of the step.
            self._pause.halt(limited, what)
        except Exception as error:
            logger.exception("Bot %s: %s failed", state.bot_id, what)
            fault_with(state, what, error)
        sent = self._context.gateway.submissions > sent_before
        if self._orders_may_rest(before, sent):
            self._park()
        self._pause.after_task()

    def _orders_may_rest(self, before: BotLifecycleState, sent: bool) -> bool:
        state = self._context.state
        return (
            state.state in _PARKED
            and (before not in _PARKED or sent)
            and state.runtime.reason not in _NOT_PARKED
        )

    def _park(self) -> None:
        try:
            report = self._housekeeping.cancel_tagged()
        except Exception as error:
            logger.exception(
                "Bot %s: taking the ladder off failed", self._context.state.bot_id
            )
            self._note(f"its orders may still rest: {error}")
            return
        if report.failed is not None:
            self._note(
                f"{report.client_order_id} and any after it may still rest: "
                f"{report.failed.detail}"
            )

    def _note(self, extra: str) -> None:
        state = self._context.state
        runtime = state.runtime
        reason = runtime.reason or GridReason.ORDER_FAILED
        state.update(runtime.with_reason(reason, f"{runtime.reason_detail}; {extra}"))
