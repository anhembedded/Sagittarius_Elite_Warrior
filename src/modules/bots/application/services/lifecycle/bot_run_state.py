"""`EPIC-029E` — the running bot's one record, and its one writer (ADR D4, D9).

Held by the bot's executor and touched only on the bot's worker. Every change
of the lifecycle goes through the table (`Bot.apply`), and every change of the
bot or its ladder is saved at once ("persist after acting": the tag makes a
write after a submit safe, because an order sent but never saved is still found
by its tag at reconciliation).

**A store that cannot write is a fact, not an exception** (`EPIC-035G`). The
memory changes first, so a save that raised left memory ahead of the file and
unwound whatever was acting, `GridTaskGuard`'s park included. `_save` now keeps
the failure (`storage_failure`) and returns, and the next write that succeeds
carries the whole true state, because every write is the whole record. It also
counts the failures in a row (`failed_saves`): `GridStorageWatch` pauses the bot
at three (owner decision D6), so it does not trade on memory indefinitely.

Each transition logs one line, `Bot <id>: <from> -> <to> on <event>`, with the
reason the runtime records when there is one (`logging-rule.md`). **The level is
the target's** (`BUG-209`): a bot that lands in HALTED is a WARNING and one that
lands in ERROR is an ERROR, because an unattended run is judged by grepping for
those levels (`LOGGING.md` §3) and the bot has stopped trading either way. This
is the one place a transition is applied, so every path into HALTED or ERROR is
covered here and no caller needs a line of its own for it. An event the table
does not declare in the bot's state is no transition: `apply_or_record` keeps
its reason and says so at WARNING.
"""

from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_runtime_codec import (
    encode_runtime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.halt_recovery_director import (
    NO_HALT_RECOVERY,
    HaltRecoveryDirector,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import Bot
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
    BotLifecycleState,
    is_declared,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.grid.grid_runtime import (
    GridReason,
    GridRuntime,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.halt_recovery_policy import (
    HaltCode,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.recovery_ledger import (
    RecoveryAttempt,
    attempts_within,
)

logger = logging.getLogger("App.Bots.GridExecutor")

#: Consecutive failed writes that pause a running bot (owner decision D6);
#: `GridStorageWatch` pauses at it, and every failure below it is logged as
#: "n/limit" with a retry to follow.
FAILED_SAVES_BEFORE_PAUSE = 3

#: The level of a transition by the state it lands in (`BUG-209`); every other
#: target is a plain decision, INFO.
_LEVEL_OF_TARGET = {
    BotLifecycleState.HALTED: logging.WARNING,
    BotLifecycleState.AWAITING_RECOVERY: logging.WARNING,
    BotLifecycleState.ERROR: logging.ERROR,
}


def landing_level(state: BotLifecycleState) -> int:
    """The log level of a bot arriving in `state`: WARNING for HALTED, ERROR for
    ERROR, INFO for the rest. The one table; the boot restore uses it too."""
    return _LEVEL_OF_TARGET.get(state, logging.INFO)


class BotRunState:
    """The bot and its ladder, saved after every change."""

    def __init__(
        self,
        bot: Bot,
        runtime: GridRuntime,
        store: IBotStore,
        clock: IBotClock,
        halts: HaltRecoveryDirector = NO_HALT_RECOVERY,
    ) -> None:
        """@param halts Decides whether a halt is one the bot recovers from by itself
        (`EPIC-042C`); the default recovers nothing, so a halt is a plain `halt`."""
        self._bot = bot
        self._halts = halts
        self._runtime = runtime
        self._store = store
        self._clock = clock
        self._storage_failure: str | None = None
        self._failed_saves = 0

    @property
    def bot(self) -> Bot:
        return self._bot

    @property
    def runtime(self) -> GridRuntime:
        return self._runtime

    @property
    def state(self) -> BotLifecycleState:
        return self._bot.state

    @property
    def bot_id(self) -> str:
        return self._bot.bot_id.value

    @property
    def storage_failure(self) -> str | None:
        """Why the last write failed, or `None` when it succeeded: memory is
        ahead of the file exactly while this is set."""
        return self._storage_failure

    @property
    def failed_saves(self) -> int:
        """How many writes in a row failed; a write that succeeds resets it."""
        return self._failed_saves

    def now(self) -> datetime:
        return self._clock.now()

    def can(self, event: BotLifecycleEvent) -> bool:
        return is_declared(self._bot.state, event)

    def update(self, runtime: GridRuntime) -> None:
        """Keep and save the ladder after a change."""
        self._runtime = runtime
        self._save()

    def transition(
        self,
        event: BotLifecycleEvent,
        reason: GridReason | None = None,
        detail: str = "",
    ) -> None:
        """Apply `event`, record `reason` when given, and save.

        @raise InvalidBotTransitionError The table does not declare it."""
        before = self._bot.state
        self._bot = self._bot.apply(event, self._clock.now())
        if reason is not None:
            self._runtime = self._runtime.with_reason(reason, detail)
        elif event is BotLifecycleEvent.START or (
            # `BUG-206` - the note "it stays paused, press Resume" is answered by Resume.
            event is BotLifecycleEvent.RESUME
            and self._runtime.reason is GridReason.RESTORED_PAUSED
        ):
            self._runtime = replace(self._runtime, reason=None, reason_detail="")
        self._save()
        logger.log(
            landing_level(self._bot.state),
            "Bot %s: %s -> %s on %s%s [bot-transition]",
            self.bot_id,
            before.value,
            self._bot.state.value,
            event.value,
            f" ({reason.value}: {detail})" if reason is not None else "",
        )

    def halt(self, reason: GridReason, detail: str) -> None:
        """Halt the bot for `reason`: `halt_transient` when the effective policy lets it recover
        by itself and its budget allows (`EPIC-042C`, ADR 042 §2.1), a plain `halt` otherwise."""
        decision = self._halts.decide(
            self._bot, HaltCode(reason.value), self._clock.now()
        )
        if decision.event is BotLifecycleEvent.HALT_TRANSIENT:
            logger.info(
                "Bot %s: %s is transient; the bot waits for it to clear [bot-halt-recovery]",
                self.bot_id,
                reason.value,
            )
            self.apply_or_record(decision.event, reason, detail)
            return
        note = f"; {decision.note}" if decision.note else ""
        self.apply_or_record(BotLifecycleEvent.HALT, reason, f"{detail}{note}")

    def record_recovery_attempt(self, code: HaltCode) -> None:
        """Count an automatic recovery as started, and save it before anything is asked of the
        exchange (ADR 042 D10): a refusal or a crash after this still spent the attempt."""
        self._bot = self._bot.with_recovery_attempt(
            RecoveryAttempt(code, self._clock.now()), self._halts.keep_for
        )
        self._save()

    def recovery_attempts_used(self, code: HaltCode) -> int:
        """How many attempts count against `code`'s rule now (every reason's, ADR 042 §2.3)."""
        rule = self._halts.rule_for(code)
        if rule is None:
            return 0
        return attempts_within(
            self._bot.lifecycle.recovery_attempts, rule.window, self._clock.now()
        )

    def apply_or_record(
        self, event: BotLifecycleEvent, reason: GridReason, detail: str
    ) -> None:
        """`transition` when the table declares `event` in the bot's state; otherwise
        keep `reason` on the record and log that the event changed nothing.

        The second case is a refusal worth a WARNING: the bot stays where it was
        while something that should have moved it (a halt, a fault) happened."""
        if self.can(event):
            self.transition(event, reason, detail)
            return
        logger.warning(
            "Bot %s: %s ignored in %s (%s: %s); the state is unchanged "
            "[bot-transition-refused]",
            self.bot_id,
            event.value,
            self._bot.state.value,
            reason.value,
            detail,
        )
        self.update(self._runtime.with_reason(reason, detail))

    def save_works(self) -> bool:
        """Write the record once more and say whether the store took it."""
        self._save()
        return self._storage_failure is None

    def _save(self) -> None:
        try:
            self._store.save(StoredBot(self._bot, encode_runtime(self._runtime)))
        except OSError as error:
            self._failed_saves += 1
            self._storage_failure = f"{type(error).__name__}: {error.strerror or error}"
            self._log_failed_save()
            return
        if self._failed_saves:
            logger.info(
                "Bot %s: state save recovered after %d failure(s) [bot-store-recovered]",
                self.bot_id,
                self._failed_saves,
            )
        self._failed_saves = 0
        self._storage_failure = None

    def _log_failed_save(self) -> None:
        """Every failed save is a log line the bot's log tab shows (`App.Bots`)."""
        if self._failed_saves < FAILED_SAVES_BEFORE_PAUSE:
            logger.warning(
                "Bot %s: state save failed (%d/%d): %s; retrying with the next write "
                "[bot-store-failed]",
                self.bot_id,
                self._failed_saves,
                FAILED_SAVES_BEFORE_PAUSE,
                self._storage_failure,
            )
            return
        logger.error(
            "Bot %s: state save failed (%d in a row, the limit of %d is reached): %s; "
            "memory is ahead of the file until a write succeeds [bot-store-failed]",
            self.bot_id,
            self._failed_saves,
            FAILED_SAVES_BEFORE_PAUSE,
            self._storage_failure,
        )
