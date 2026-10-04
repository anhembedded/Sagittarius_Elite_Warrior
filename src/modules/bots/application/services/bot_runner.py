"""`EPIC-029E` — `IBotRunner`: start's preconditions, then the executor (ADR §3.1, D9)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_executors import (
    BotExecutors,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_executor import (
    GridExecutor,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.grid_start_preconditions import (
    GridStartPreconditions,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import (
    IBotStore,
    StoredBot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_id import BotId
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    RUN_STARTING_STATES,
    BotLifecycleEvent,
    InvalidBotTransitionError,
)


class BotRunner(IBotRunner):
    """Starts a bot through its preconditions and queues every other command."""

    def __init__(
        self,
        store: IBotStore,
        clock: IBotClock,
        preconditions: GridStartPreconditions,
        executors: BotExecutors,
    ) -> None:
        self._store = store
        self._clock = clock
        self._lookup = BotLookup(store)
        self._preconditions = preconditions
        self._executors = executors

    def start(self, bot_id: str) -> BotCommandResult:
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

    def resume(self, bot_id: str) -> None:
        self._executor(bot_id).resume()

    def stop(self, bot_id: str, base: BaseHandling) -> None:
        self._executor(bot_id).stop(base)

    def confirm_resume(self, bot_id: str) -> None:
        self._executor(bot_id).confirm_resume()

    def has_resume_proposal(self, bot_id: str) -> bool:
        return self._executor(bot_id).has_resume_proposal()

    def _executor(self, bot_id: str) -> GridExecutor:
        """@raise BotNotFoundError The bot is gone (the use case found it a
        moment ago). @raise UnreadableBotError Its file cannot be read."""
        return self._executors.for_bot(self._store.load(BotId(bot_id)).bot)
