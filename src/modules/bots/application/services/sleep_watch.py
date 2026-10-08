"""`EPIC-035I` — what the bots module does when the machine slept.

A suspended laptop stops the process: the price stream dies, the user-data
stream with it, and every fill and price move of the night goes unseen. When the
heartbeat finds it has been away (`ClockGapDetector`), this service does for
every bot what a stream that came back does, and one thing more:

  1. **Catch up.** Each executor's `reconcile_after_gap()` — the entry point
     `EPIC-035B`'s `UserStreamWatch` uses, not a second reconcile — brings the
     ladder level with the exchange's open orders and trade history.
  2. **Check the exits.** `WakeExitCheck` reads a fresh price and gives it to
     each bot, so a stop loss crossed in sleep is taken now, not at the next tick.
  3. **Say so.** One line in the log naming the gap, one notice to the user.

The catch-up goes first and the price after it, on each bot's own queue, so a
fill the night held is booked before the exit rule looks at the price.

@par Extension cases (`architecture-rule.md` §7.2.1)
  · a bot kind other than Grid — nothing here changes: it rides `IBotExecutor`;
  · the per-bot health strip (`EPIC-035W`) shows the last wake — it reads the
    same log line's facts from a snapshot, no change here;
  · a platform power event instead of a clock gap — one more caller of `_wake`.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_notifier import INotifier
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.clock_gap_detector import (
    ClockGapDetector,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.wake_exit_check import (
    WakeExitCheck,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_retry_scheduler import (
    IBotRetryScheduler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_fresh_price_reader import (
    IFreshPriceReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_monotonic_clock import (
    IMonotonicClock,
)

logger = logging.getLogger("App.Bots.Sleep")


@dataclass(frozen=True, slots=True)
class SleepLimits:
    """The durations and counts of the sleep rule, named once."""

    #: How often the heartbeat looks at the clocks: the precision of the rest.
    check_every: timedelta = timedelta(seconds=15)
    #: A look this much later than expected is a sleep. A minute rides out a busy
    #: machine and a slow heartbeat without calling either a sleep.
    gap_over: timedelta = timedelta(seconds=60)
    #: Reads of the fresh price before the wake leaves a bot to the staleness rule.
    price_attempts: int = 4
    price_retry_every: timedelta = timedelta(seconds=15)

    def __post_init__(self) -> None:
        for name in ("check_every", "gap_over", "price_retry_every"):
            if getattr(self, name) <= timedelta(0):
                raise ValueError(f"{name} must be positive")
        if self.price_attempts < 1:
            raise ValueError("price_attempts must be at least 1")


DEFAULT_SLEEP_LIMITS = SleepLimits()


@dataclass(frozen=True, slots=True)
class SleepWatchDeps:
    """What the watch reads and uses besides the bots."""

    monotonic: IMonotonicClock
    wall: IBotClock
    retries: IBotRetryScheduler
    prices: IFreshPriceReader
    notifier: INotifier


class SleepWatch:
    """Notices a sleep and catches every bot up from it."""

    def __init__(
        self,
        executors: BotExecutors,
        deps: SleepWatchDeps,
        limits: SleepLimits = DEFAULT_SLEEP_LIMITS,
    ) -> None:
        self._executors = executors
        self._deps = deps
        self._limits = limits
        self._detector = ClockGapDetector(deps.monotonic, deps.wall, limits.gap_over)
        self._exits = WakeExitCheck(
            executors,
            deps.prices,
            deps.retries,
            (limits.price_attempts, limits.price_retry_every),
        )

    def begin(self) -> None:
        """Start the heartbeat: `check()` every `check_every` until the
        scheduler is closed."""
        self._deps.retries.after(self._limits.check_every, self._beat)

    def _beat(self) -> None:
        try:
            self.check()
        finally:
            self._deps.retries.after(self._limits.check_every, self._beat)

    def check(self) -> None:
        """One look at the clocks; a gap is caught up from."""
        away = self._detector.look(self._limits.check_every)
        if away is not None:
            self._wake(away)

    def _wake(self, away: timedelta) -> None:
        executors = self._executors.all()
        logger.info(
            "The machine was away %d s; catching %d bot(s) up [sleep-detected]",
            int(away.total_seconds()),
            len(executors),
        )
        if not executors:
            return
        for executor in executors:
            executor.reconcile_after_gap()
        self._exits.begin()
        count = len(executors)
        self._deps.notifier.notify(
            f"The computer was asleep {_duration_text(away)}; "
            f"{count} bot{'s' if count != 1 else ''} re-checked against the exchange",
            "Fills missed while asleep were recovered and each stop loss and "
            "take profit was checked against a fresh price.",
        )


def _duration_text(span: timedelta) -> str:
    minutes = int(span.total_seconds() // 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours} h {minutes} min"
    return f"{minutes} min"
