"""`EPIC-035C` (H5) — a stop that waits on the exchange retries itself, boundedly.

A stop waits in STOPPING when a cancel was refused, an order the exchange had
not yet removed was still open, or a read did not answer. Its only retry used
to be a trading session closed → open event, so a bot could stay STOPPING
indefinitely. Now:

  · the executor schedules a retry after each such wait, on `STOP_RETRY_DELAYS`
    (a named, bounded backoff), and the bot's reason says the retry number and
    when it comes;
  · the user can ask again: `stop` is declared in STOPPING and starts a fresh
    round, so a retry already scheduled by an earlier round is ignored;
  · after the last retry the bot stays STOPPING with a reason naming the next
    action (press Stop), and the exhaustion is an ERROR log record with the bot
    id until an alert channel exists (`EPIC-035K`).

A wait on the order session (trading is off) is not retried on a timer: the
switch-on event runs the stop again, and a timer would only be refused.
STOPPED still requires zero open tagged orders (`GridStopSequence._confirm`);
nothing here can raise `stop_confirmed`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_run_context import (
    GridRunContext,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_stop_sequence import (
    StopProgress,
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
    AUTO_RESUME_MARGIN,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: The wait before each automatic retry of a stop: five retries in about nine
#: minutes. Short first (a cancel the exchange just has not applied), longer
#: after (an exchange or a network that needs a moment), then the user decides.
STOP_RETRY_DELAYS: tuple[timedelta, ...] = (
    timedelta(seconds=10),
    timedelta(seconds=30),
    timedelta(seconds=60),
    timedelta(seconds=120),
    timedelta(seconds=300),
)


class GridStopRetry:
    """The retry rounds of one bot's stop."""

    def __init__(
        self,
        context: GridRunContext,
        scheduler: IBotRetryScheduler,
        post: Callable[[str, Callable[[], None]], None],
    ) -> None:
        self._context = context
        self._scheduler = scheduler
        self._post = post
        self._round = 0
        self._retries_run = 0

    def begin_round(self) -> None:
        """A stop the user or an event asked for: retries scheduled by an
        earlier round are stale from now on, and the count starts over."""
        self._round += 1
        self._retries_run = 0

    def settle(self, progress: StopProgress, run_again: Callable[[], None]) -> None:
        """Schedule the next retry for a stop that waits on the exchange, give
        up when the delays are used up, and do nothing for any other end."""
        if progress is not StopProgress.WAITING_ON_EXCHANGE:
            return
        if self._retries_run >= len(STOP_RETRY_DELAYS):
            self._exhausted()
            return
        delay = STOP_RETRY_DELAYS[self._retries_run]
        pause = self._context.gateway.take_rate_limit()
        if pause is not None:
            # `EPIC-035D` — a retry inside the exchange's pause would only be refused.
            delay = max(delay, pause + AUTO_RESUME_MARGIN)
        number = self._retries_run + 1
        self._append(f"retry {number} of {len(STOP_RETRY_DELAYS)} in {_seconds(delay)}")
        round_ = self._round
        self._scheduler.after(
            delay,
            lambda: self._post("stop retry", lambda: self._retry(round_, run_again)),
        )

    def _retry(self, round_: int, run_again: Callable[[], None]) -> None:
        if round_ != self._round:
            return
        if self._context.state.state is not BotLifecycleState.STOPPING:
            return
        self._retries_run += 1
        run_again()

    def _exhausted(self) -> None:
        state = self._context.state
        self._append(
            f"the {len(STOP_RETRY_DELAYS)} automatic retries are used up; "
            "press Stop to try again"
        )
        logger.error(
            "Bot %s: STOPPING after %d automatic retries — %s",
            state.bot_id,
            len(STOP_RETRY_DELAYS),
            state.runtime.reason_detail,
        )

    def _append(self, text: str) -> None:
        state = self._context.state
        runtime = state.runtime
        reason = runtime.reason or GridReason.USER_STOP
        state.update(runtime.with_reason(reason, f"{runtime.reason_detail}; {text}"))


def _seconds(delay: timedelta) -> str:
    return f"{int(delay.total_seconds())}s"
