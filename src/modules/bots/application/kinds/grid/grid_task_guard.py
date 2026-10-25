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
    then, and the orders rest by design (D13). So is a rejected API key
    (`EPIC-035F`): the cancel would be rejected too, so the bot says its orders
    may still rest and this app cannot cancel them, and tries nothing. What
    could not be cancelled is named beside the reason, never replacing it.

**Parking does not depend on the disk** (`EPIC-035G`): `BotRunState` keeps a
failed write as `storage_failure` instead of raising it, so the fault handler
and the park both run. The failure is named beside the reason, never in its
place, and the next write that succeeds persists it with the true state.

**A store that keeps failing pauses a running bot** (`EPIC-035G`, D6): after each
task `GridStorageWatch` pauses a RUNNING bot whose last three writes failed.

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

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    fault_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_parking import (
    GridParking,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.recovery.grid_covered_wait import (
    GridCoveredWait,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_rate_limit_pause import (
    GridRateLimitPause,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.watch.grid_storage_watch import (
    GridStorageWatch,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
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

logger = logging.getLogger("App.Bots.GridExecutor")

#: The states a bot takes its ladder off the exchange on entering, unless
#: trading switched off.
_PARKED: frozenset[BotLifecycleState] = frozenset(
    {
        BotLifecycleState.HALTED,
        BotLifecycleState.AWAITING_RECOVERY,
        BotLifecycleState.ERROR,
    }
)

#: Halts that come from a closed order session, where a cancel would be refused:
#: the ladder rests by design (D13), and a start it cut short owes the cancel
#: instead (`BUG-190`). A rejected API key (`EPIC-035F`) is the other: the cancel
#: would be rejected too.
_NOT_PARKED: frozenset[GridReason] = frozenset(
    {
        GridReason.SWITCH_OFF,
        GridReason.START_CUT_BY_SWITCH_OFF,
        GridReason.KEY_REJECTED,
        GridReason.RATE_LIMITED,
    }
)


#: What a halt says when its own cancel failed and the stop that closed the position then took
#: the ladder off (`GridParking`): a stopped bot has no order left.
_CANCEL_FAILED_STOP_TOOK_IT_OFF = (
    "the halt's own cancel did not go through, and the stop that closed the position "
    "took the ladder off"
)


#: How a parked bot says its file is behind; also what keeps the note single.
_STORAGE_NOTE = "its state could not be saved"


class GridTaskGuard:
    """Runs one worker task, then parks the ladder if the task stopped placing."""

    def __init__(
        self,
        context: GridRunContext,
        parking: GridParking,
        pause: GridRateLimitPause,
        storage: GridStorageWatch,
        covered_wait: GridCoveredWait,
    ) -> None:
        self._context = context
        self._covered_wait = covered_wait
        self._parking = parking
        self._pause = pause
        self._storage = storage

    def run(self, what: str, task: Callable[[], None]) -> None:
        """Run `task`, named `what` in any fault it becomes."""
        state = self._context.state
        before = state.state
        kept_before = self._covered_wait.holds()
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
        if self._orders_may_rest(before, sent, kept_before):
            self._park()
        elif self._halted_unable_to_park(before, sent):
            self._say_position_stays_open()
        if self._unsaved_and_parked():
            self._note(f"{_STORAGE_NOTE} ({state.storage_failure})")
        self._pause.after_task()
        self._storage.pause_if_failing()

    def _orders_may_rest(
        self, before: BotLifecycleState, sent: bool, kept_before: bool
    ) -> bool:
        """A wait under the stop (`GridCoveredWait`) keeps its ladder, so entering it parks nothing,
        and leaving it for a halt is a park: the ladder was never taken off (`BUG-269`)."""
        state = self._context.state
        return (
            state.state in _PARKED
            and not self._covered_wait.holds()
            and (before not in _PARKED or kept_before or sent)
            and state.runtime.reason not in _NOT_PARKED
        )

    def _halted_unable_to_park(self, before: BotLifecycleState, sent: bool) -> bool:
        """A halt just made, for a reason that sends no cancel (`_NOT_PARKED`)."""
        state = self._context.state
        return (
            state.state in _PARKED
            and (before not in _PARKED or sent)
            and state.runtime.reason in _NOT_PARKED
        )

    def _say_position_stays_open(self) -> None:
        words = self._parking.left_open_words()
        if words is not None and words not in self._context.state.runtime.reason_detail:
            self._note(words)

    def _unsaved_and_parked(self) -> bool:
        """A parked bot whose file is behind, and which does not say so yet."""
        state = self._context.state
        return (
            state.storage_failure is not None
            and state.state in _PARKED
            and _STORAGE_NOTE not in state.runtime.reason_detail
        )

    def _park(self) -> None:
        try:
            note = self._parking.park()
        except ExchangeRateLimitedError as limited:
            note = self._pause_met_while_parking(limited)
        except Exception as error:
            logger.exception(
                "Bot %s: taking the ladder off failed", self._context.state.bot_id
            )
            note = f"its orders may still rest: {error}"
        if note is None:
            return
        if self._context.state.state is BotLifecycleState.AWAITING_RECOVERY:
            self._halt_unparked(note)
            return
        if self._context.state.state is BotLifecycleState.STOPPED:
            # A venue that closes on a halt ran the stop after the failed cancel, and a stop
            # is only STOPPED once it read zero orders of the bot's: say what happened, not
            # what might have.
            note = _CANCEL_FAILED_STOP_TOOK_IT_OFF
        self._note(note)

    def _pause_met_while_parking(self, limited: ExchangeRateLimitedError) -> str | None:
        """The exchange's pause stopped the cancel (`BUG-257`): told once as `[exchange-pause]`, not
        as an ERROR with a traceback. A bot that holds no order, a refused start that laid no
        ladder, has nothing resting to name, so the note is empty; one that does hold orders says
        they may still rest."""
        state = self._context.state
        logger.info(
            "Bot %s: taking the ladder off waits for the exchange's pause of %d s "
            "[exchange-pause]",
            state.bot_id,
            whole_seconds(limited.retry_after),
        )
        if not state.runtime.open_orders:
            return None
        return (
            "its orders may still rest: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s"
        )

    def _halt_unparked(self, note: str) -> None:
        """A wait whose premise is a ladder off the exchange cannot stand when the cancel was
        lost (the outage that caused the halt is often the network): the bot lands in plain
        HALTED, where the halt alert says its orders may still rest and a person decides
        (`EPIC-042C`, review of PR #552)."""
        state = self._context.state
        runtime = state.runtime
        state.transition(
            BotLifecycleEvent.HALT,
            runtime.reason,
            f"{runtime.reason_detail}; {note}; it does not wait to recover because its "
            "orders may still rest",
        )

    def _note(self, extra: str) -> None:
        state = self._context.state
        runtime = state.runtime
        reason = runtime.reason or GridReason.ORDER_FAILED
        state.update(runtime.with_reason(reason, f"{runtime.reason_detail}; {extra}"))
