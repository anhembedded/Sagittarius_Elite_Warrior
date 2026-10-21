"""`EPIC-035D`, `EPIC-042F` — a Grid met by a rate limit waits for the pause on the halt-recovery mechanism.

HTTP 429, `-1003`, `-1015` and a 418 ban used to reach the lifecycle as a request that raised:
ERROR, whose only exit is a manual Stop and Start. They are a pause the exchange named, so the bot
halts for exactly that long (`GridReason.RATE_LIMITED`, the pause in its reason).

Since `EPIC-042F` that halt is a *transient* one like a quiet feed (ADR 042): the bot waits in
AWAITING_RECOVERY, the Grid's kind layer holds the rule (`GRID_RECOVERY_LAYER`: the common budget,
three recoveries per rolling 24 h, and a dwell of `AUTO_RESUME_MARGIN`), and the probe is *the
pause has ended* (`holds`, read by `GridHaltProbe`). The attempt is the one a person's Resume runs
(`GridResumeSequence`) with the exits re-checked on a fresh price first (`GridHaltRecovery`): the
budget is registered again, every tagged order is taken off, a fresh ladder is proposed from the
price now and the inventory the exchange shows, then laid. That is why a rate-limit halt does not
park: the cancels would be refused inside the pause, and the attempt cancels everything tagged
first anyway.

What the mechanism does not wait for is left to a person, saying so: a pause longer than
`MAX_AUTO_RESUME_WAIT`, the spent budget, and a bot the policy never recovers (PAUSED, RECOVERING,
or HALTED, which only a person leaves). A limit met by a bot already waiting for something else
does not change its reason or its dwell: the pause only joins what the wait watches.

This class keeps the one fact the probe needs and the halt cannot carry: *when the pause the bot
met ends*, on the bot's monotonic clock, in memory (a restart ends the wait in HALTED, D9, and
the exchange's pause is long over by the time a person resumes). Touched only on the bot's worker.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_order_failure import (
    pause_with,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
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

_S = BotLifecycleState

#: The states a rate limit halts: those that place orders or wait to, and HALTED
#: itself (a resume the user asked for that met the limit). Not STOPPING (its stop
#: waits out the pause, `GridStopSequence`), not ERROR, which only Stop leaves.
_HALTED_BY_A_LIMIT: frozenset[BotLifecycleState] = frozenset(
    {
        _S.STARTING,
        _S.RUNNING,
        _S.PAUSED,
        _S.RECOVERING,
        _S.HALTED,
        _S.AWAITING_RECOVERY,
    }
)

#: What a bot says when the limit left it HALTED: the mechanism does not recover that state.
_BY_HAND = "it does not resume by itself from here; resume by hand once the pause ends"
_BY_HAND_MARK = "resume by hand"


class GridRateLimitPause:
    """Halts a bot for a rate limit and knows when the pause it met ends."""

    def __init__(self, context: GridRunContext) -> None:
        self._context = context
        #: When the pause the bot last met ends, in `monotonic` seconds; `None` before any.
        self._ends_at: float | None = None

    def holds(self) -> bool:
        """Whether the pause this bot met is still running: the recovery probe's `rate_limited`
        is *clear* when it is not. A bot that met none is not held."""
        ends_at = self._ends_at
        return ends_at is not None and self._context.monotonic.seconds() < ends_at

    def halt(self, limited: ExchangeRateLimitedError, what: str) -> None:
        """A task raised the limit (a read, or a request outside an order): halt the bot for it.
        `after_task` then records when the pause ends."""
        self._context.gateway.note_rate_limit(limited.retry_after)
        state = self._context.state
        if state.state not in _HALTED_BY_A_LIMIT or not state.may_hold_exposure:
            logger.warning(
                "Bot %s: %s met a rate limit in %s; left as it is",
                state.bot_id,
                what,
                state.state.value,
            )
            return
        pause_with(
            state,
            limited.retry_after,
            f"{what}: rate limited: the exchange asked for a pause of "
            f"{whole_seconds(limited.retry_after)} s",
        )

    def after_task(self) -> None:
        """Record when the pause this task met ends, and say what the bot does about it."""
        pause = self._context.gateway.take_rate_limit()
        if pause is None:
            return
        state = self._context.state
        if state.state is _S.AWAITING_RECOVERY:
            self._hold(pause)
        elif (
            state.state is _S.HALTED and state.runtime.reason is GridReason.RATE_LIMITED
        ):
            self._say(_BY_HAND, unless=_BY_HAND_MARK)

    def _hold(self, pause: timedelta) -> None:
        state = self._context.state
        ends_at = self._context.monotonic.seconds() + pause.total_seconds()
        self._ends_at = (
            ends_at if self._ends_at is None else max(self._ends_at, ends_at)
        )
        seconds = whole_seconds(pause)
        logger.info(
            "Bot %s: waiting for the exchange's pause of %d s to end [bot-rate-limit-wait]",
            state.bot_id,
            seconds,
        )
        if state.runtime.reason is GridReason.RATE_LIMITED:
            self._say(
                "resumes by itself when the pause ends", unless="resumes by itself"
            )
        else:
            self._say(
                f"the exchange also asked for a pause of {seconds} s; "
                "the wait lasts until it ends too",
                unless="the exchange also asked",
            )

    def _say(self, text: str, *, unless: str) -> None:
        """Add `text` to the reason's detail once: not when `unless` is already in it."""
        state = self._context.state
        runtime = state.runtime
        if runtime.reason is None or unless in runtime.reason_detail:
            return
        state.update(
            runtime.with_reason(runtime.reason, f"{runtime.reason_detail}; {text}")
        )
