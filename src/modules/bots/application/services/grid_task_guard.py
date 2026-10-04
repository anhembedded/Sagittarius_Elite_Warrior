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
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The states a bot takes its ladder off the exchange on entering, unless
#: trading switched off.
_PARKED: frozenset[BotLifecycleState] = frozenset(
    {BotLifecycleState.HALTED, BotLifecycleState.ERROR}
)


class GridTaskGuard:
    """Runs one worker task, then parks the ladder if the task stopped placing."""

    def __init__(self, context: GridRunContext, housekeeping: GridHousekeeping) -> None:
        self._context = context
        self._housekeeping = housekeeping

    def run(self, what: str, task: Callable[[], None]) -> None:
        """Run `task`, named `what` in any fault it becomes."""
        state = self._context.state
        before = state.state
        try:
            task()
        except Exception as error:
            logger.exception("Bot %s: %s failed", state.bot_id, what)
            fault_with(state, what, error)
        if self._stopped_placing_since(before):
            self._park()

    def _stopped_placing_since(self, before: BotLifecycleState) -> bool:
        state = self._context.state
        return (
            state.state in _PARKED
            and before not in _PARKED
            and state.runtime.reason is not GridReason.SWITCH_OFF
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
