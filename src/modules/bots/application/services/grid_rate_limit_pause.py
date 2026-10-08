"""`EPIC-035D` (M3) — a Grid halted by a rate limit resumes by itself when the pause ends.

HTTP 429, `-1003`, `-1015` and a 418 ban used to reach the lifecycle as a request
that raised: ERROR, whose only exit is a manual Stop and Start. They are a pause
the exchange named, so the bot halts for exactly that long (`GridReason.RATE_LIMITED`,
the pause in its reason) and a resume is scheduled on the bot's retry scheduler
(`IBotRetryScheduler`, the seam of `EPIC-035C`; no timer or clock is added here).

The resume is the one a user's Resume and Confirm run (`GridResumeSequence`): the
budget is registered again, every tagged order is taken off, and a fresh ladder is
proposed from the price now and the inventory the exchange shows, then laid. That is
why a rate-limit halt does not park: the cancels would be refused inside the pause,
and the resume cancels everything tagged first anyway.

It is bounded (`rate_limit_pause.py`): a pause too long for a timer, or a limit that
keeps coming back, leaves the bot HALTED with a reason that says to resume by hand.
A resume scheduled before the user acted, or before another halt, does nothing:
it runs only for the round it was scheduled in, and only on a bot still HALTED for
a rate limit. Touched only on the bot's worker.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_order_failure import (
    halt_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_resume_sequence import (
    GridResumeSequence,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.rate_limit_pause import (
    MAX_AUTO_RESUME_WAIT,
    MAX_AUTO_RESUMES,
    resume_delay,
    whole_seconds,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_rate_limited_error import (
    ExchangeRateLimitedError,
)

logger = logging.getLogger("App.Bots.GridExecutor")

_S = BotLifecycleState

#: The states a rate limit halts: those that place orders or wait to, and HALTED
#: itself (a resume the user asked for that met the limit). Not STOPPING (its stop
#: waits out the pause, `GridStopSequence`), not ERROR, which only Stop leaves.
_HALTED_BY_A_LIMIT: frozenset[BotLifecycleState] = frozenset(
    {_S.STARTING, _S.RUNNING, _S.PAUSED, _S.RECOVERING, _S.HALTED}
)


class GridRateLimitPause:
    """Halts a bot for a rate limit and schedules its resume for the pause's end."""

    def __init__(
        self,
        context: GridRunContext,
        retries: IBotRetryScheduler,
        post: Callable[[str, Callable[[], None]], None],
        resume: GridResumeSequence,
        price: Callable[[], Decimal],
    ) -> None:
        self._context = context
        self._retries = retries
        self._post = post
        self._resume = resume
        self._price = price
        self._round = 0
        self._automatic_resumes = 0

    def halt(self, limited: ExchangeRateLimitedError, what: str) -> None:
        """A task raised the limit (a read, or a request outside an order): halt
        the bot for it. `after_task` then schedules the resume."""
        self._context.gateway.note_rate_limit(limited.retry_after)
        state = self._context.state
        if state.state not in _HALTED_BY_A_LIMIT:
            logger.warning(
                "Bot %s: %s met a rate limit in %s; left as it is",
                state.bot_id,
                what,
                state.state.value,
            )
            return
        halt_with(
            state,
            GridReason.RATE_LIMITED,
            f"{what}: rate limited: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s",
        )

    def after_task(self) -> None:
        """Schedule the resume when this task left the bot HALTED for a limit."""
        pause = self._context.gateway.take_rate_limit()
        state = self._context.state
        if (
            pause is None
            or state.state is not _S.HALTED
            or state.runtime.reason is not GridReason.RATE_LIMITED
        ):
            return
        delay = resume_delay(pause)
        if delay is None:
            self._append(
                f"the pause is longer than {whole_seconds(MAX_AUTO_RESUME_WAIT)} s, "
                "which no timer holds; resume by hand once it ends"
            )
            return
        if self._automatic_resumes >= MAX_AUTO_RESUMES:
            self._append(
                f"the {MAX_AUTO_RESUMES} automatic resumes are used up; resume by hand"
            )
            logger.error(
                "Bot %s: HALTED by a rate limit after %d automatic resumes [bot-rate-limit-exhausted]",
                state.bot_id,
                MAX_AUTO_RESUMES,
            )
            return
        self._round += 1
        round_ = self._round
        self._append(f"resumes by itself in {whole_seconds(delay)} s")
        self._retries.after(
            delay,
            lambda: self._post("rate-limit resume", lambda: self._resume_now(round_)),
        )

    def _resume_now(self, round_: int) -> None:
        state = self._context.state
        if (
            round_ != self._round
            or state.state is not _S.HALTED
            or state.runtime.reason is not GridReason.RATE_LIMITED
        ):
            return
        self._automatic_resumes += 1
        logger.info(
            "Bot %s: resuming after a rate limit (automatic resume %d of %d) [bot-rate-limit-resume]",
            state.bot_id,
            self._automatic_resumes,
            MAX_AUTO_RESUMES,
        )
        proposal = self._resume.propose(self._price())
        if proposal is not None:
            self._resume.confirm(proposal)
        if self._context.state.state is _S.RUNNING:
            self._automatic_resumes = 0

    def _append(self, text: str) -> None:
        state = self._context.state
        runtime = state.runtime
        reason = runtime.reason or GridReason.RATE_LIMITED
        state.update(runtime.with_reason(reason, f"{runtime.reason_detail}; {text}"))
