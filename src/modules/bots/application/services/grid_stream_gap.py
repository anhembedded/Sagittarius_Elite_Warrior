"""`EPIC-035B` — what a running Grid does about its user-data stream.

The stream is the only source of fills. Two facts about it reach a bot, both
posted onto its queue like every other fact (`GridExecutor`):

  · **The stream was down and is back, or a periodic check came due**
    (`reconcile`): bring the ladder level with the exchange's open orders and
    trade history through `GridReconciler`'s missed-fill logic, then release
    the counter orders a missed fill owes (held while PAUSED). Idempotent: with
    nothing missed it changes nothing and places nothing. It is a safety net,
    so a read that fails is logged and retried at the next interval, never a
    fault of a healthy bot.
  · **The stream has been down too long** (`halt`): the bot cannot see its own
    fills, so it halts with a named reason and `GridTaskGuard` takes its ladder
    off the exchange. A stream that comes back does not resume it; the owner
    does, as for every other HALT.

The rule's strength is exactly that: it defeats *our own queue* (an event
behind the run), not the exchange's read lag, because the second run follows at
once. A run that reaches no verdict (the venue did not answer, a read raised)
clears the pending strike: two disagreements five minutes apart with a flaky
venue between them are two first sightings.

Only RUNNING and PAUSED bots act on either: a bot in any other state holds no
ladder this stream feeds (HALTED and ERROR were parked, STOPPING finishes its
own stop, RECOVERING reconciles on the trading switch).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_reconciler import (
    GridReconciler,
    ReconcileMismatch,
    ReconcileWait,
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

_FED_BY_THE_STREAM: frozenset[BotLifecycleState] = frozenset(
    {BotLifecycleState.RUNNING, BotLifecycleState.PAUSED}
)


class GridStreamGap:
    """Catches a running Grid up after a gap, and halts it when the gap lasts."""

    def __init__(
        self,
        context: GridRunContext,
        reconciler: GridReconciler,
        release_held: Callable[[], None],
        post: Callable[[str, Callable[[], None]], None],
    ) -> None:
        self._context = context
        self._reconciler = reconciler
        self._release_held = release_held
        self._post = post
        #: The disagreement the last run found and has asked a second run to
        #: confirm; touched only on the bot's worker.
        self._unconfirmed: ReconcileMismatch | None = None

    def reconcile(self) -> None:
        state = self._context.state
        if state.state not in _FED_BY_THE_STREAM:
            self._unconfirmed = None
            return
        before = state.runtime
        try:
            outcome = self._reconciler.compare_with_exchange()
        # Converted at the seam: a safety-net read that raised (the venue did
        # not answer) must not fault a bot whose ladder is fine. The traceback
        # is logged; the next interval retries.
        except Exception:
            self._unconfirmed = None
            logger.exception(
                "Bot %s: gap reconcile failed; retrying later", state.bot_id
            )
            return
        if isinstance(outcome, ReconcileWait):
            self._unconfirmed = None
            logger.info("Bot %s: gap reconcile waits: %s", state.bot_id, outcome.detail)
        elif isinstance(outcome, ReconcileMismatch):
            self._disagree(outcome)
        else:
            self._unconfirmed = None
            state.update(outcome)
            if state.state is BotLifecycleState.RUNNING:
                self._release_held()
            level = logging.INFO if state.runtime != before else logging.DEBUG
            logger.log(level, "Bot %s: gap reconcile done", state.bot_id)

    def halt(self, down_for: timedelta) -> None:
        state = self._context.state
        if state.state not in _FED_BY_THE_STREAM:
            return
        halt_with(
            state,
            GridReason.USER_STREAM_DOWN,
            "the exchange stream that reports fills has been down "
            f"{int(down_for.total_seconds())} s; the ladder was taken off",
        )

    def _disagree(self, found: ReconcileMismatch) -> None:
        state = self._context.state
        if self._unconfirmed is None:
            self._unconfirmed = found
            logger.warning(
                "Bot %s: gap reconcile disagrees (%s: %s); confirming with a second run",
                state.bot_id,
                found.reason.value,
                found.detail,
            )
            self._post("confirm a disagreement after a stream gap", self.reconcile)
            return
        self._unconfirmed = None
        halt_with(state, found.reason, found.detail)
