"""`EPIC-029E` — `IBotRunner`: start's preconditions, then the executor (ADR §3.1, D9)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.start.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.lifecycle.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_stop_coverage import (
    StopCoverageReading,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    ExposureHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RESUME_PROPOSES_STATES,
    RUN_STARTING_STATES,
    BotLifecycleEvent,
    BotLifecycleState,
    InvalidBotTransitionError,
)

if TYPE_CHECKING:
    from Sagittarius_Elite_Warrior.src.modules.bots.application.kinds.grid.grid_executor import (
        GridExecutor,
    )

#: The states whose Resume opens the venue's order session first (`BUG-202`, `BUG-204`):
#: those that propose a ladder (`RESUME_PROPOSES_STATES`) register a budget a closed session
#: refuses; RECOVERING waits for the session a restart leaves closed, then reconciles.
_RESUMES_AFTER_A_CLOSED_SESSION: frozenset[BotLifecycleState] = (
    RESUME_PROPOSES_STATES | {BotLifecycleState.RECOVERING}
)


class BotRunner(IBotRunner):
    """Starts a bot through its preconditions and queues every other command."""

    def __init__(
        self,
        store: IBotStore,
        clock: IBotClock,
        preconditions: GridStartPreconditions,
        executors: BotExecutors,
        loss_cap: ILossCapHold,
    ) -> None:
        self._store = store
        self._clock = clock
        self._lookup = BotLookup(store)
        self._preconditions = preconditions
        self._executors = executors
        self._loss_cap = loss_cap

    def start(self, bot_id: str) -> BotCommandResult:
        held = self._loss_cap_refusal(bot_id)
        if held is not None:
            return held
        found = self._lookup.find(bot_id)
        if isinstance(found, BotCommandResult):
            return found
        if found.bot.state in RUN_STARTING_STATES:
            # An earlier run's worker drains before this run writes the file.
            self._executors.retire(bot_id)
            found = self._lookup.find(bot_id)
            if isinstance(found, BotCommandResult):
                return found
        now = self._clock.now()
        try:
            started = found.bot.apply(BotLifecycleEvent.START, now)
        except InvalidBotTransitionError as exc:
            return BotCommandResult.refused(
                BotRefusal.INVALID_TRANSITION, str(exc), bot_id
            )
        refusal = self._preconditions.check(found.bot, now)
        if refusal is not None:
            return refusal
        self._store.save(StoredBot(started, {}))
        self._executors.fresh(started).start()
        return BotCommandResult.done(bot_id)

    def pause(self, bot_id: str) -> None:
        self._executor(bot_id).pause()

    def resume(self, bot_id: str) -> BotCommandResult:
        held = self._loss_cap_refusal(bot_id)
        if held is not None:
            return held
        found = self._lookup.find(bot_id)
        if isinstance(found, BotCommandResult):
            return found
        if found.bot.state in _RESUMES_AFTER_A_CLOSED_SESSION:
            refusal = self._preconditions.open_session_for_resume(found.bot)
            if refusal is not None:
                return refusal
        self._executor(bot_id).resume()
        return BotCommandResult.done(bot_id)

    def stop(self, bot_id: str, base: ExposureHandling) -> None:
        self._executor(bot_id).stop(base)

    def confirm_resume(self, bot_id: str) -> None:
        self._executor(bot_id).confirm_resume()

    def withdraw_resume_proposal(self, bot_id: str) -> None:
        self._executor(bot_id).withdraw_resume_proposal()

    def has_resume_proposal(self, bot_id: str) -> bool:
        return self._executor(bot_id).has_resume_proposal()

    def stop_coverage(self, bot_id: str) -> StopCoverageReading:
        return self._executor(bot_id).stop_coverage()

    def _loss_cap_refusal(self, bot_id: str) -> BotCommandResult | None:
        """`EPIC-026L`: a tripped account-level loss cap holds every bot down until the owner
        acknowledges it; the one place every start and every resume passes."""
        sentence = self._loss_cap.restart_refusal()
        if sentence is None:
            return None
        return BotCommandResult.refused(BotRefusal.LOSS_CAP_TRIPPED, sentence, bot_id)

    def _executor(self, bot_id: str) -> GridExecutor:
        """@raise BotNotFoundError The bot is gone (the use case found it a
        moment ago). @raise UnreadableBotError Its file cannot be read."""
        return self._executors.for_bot(self._store.load(BotId(bot_id)).bot)
