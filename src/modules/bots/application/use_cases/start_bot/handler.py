"""`EPIC-029B`, `EPIC-034H` — handler for `StartBotCommand`.

Start asks `BotReadinessReader` first, **before any order and before anything is
saved**: the same assessment the Bots screen shows, so a click is refused for
exactly what the screen listed ("N things left: …"), in the same words. It
holds the Connect step (the account is read), the Design step (every blocking
constraint on the plan, the balance and the key included) and the Run step
that is knowable without the exchange: the venue, no other bot active (ADR
D20), the symbol's lease, the owner budget's caps.

**The D20 check and the start are one step** (the PR #318 review): the
readiness and the start run under `BotCommandLock`, so two starts dispatched at
once cannot both find no other bot active.

Then `IBotRunner.start` takes the steps that touch the session and can still be
refused by a race or by the exchange (`GridStartPreconditions`): the lease, the
reconciliation, the budget's registration; then STARTING and the queued start.

With `config` (**Save and Start**, D8) the parameters are judged **as they
would be saved**; only a bot that is ready with them is saved, then started, so
a refused start never leaves edits half-applied.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_lock import (
    BotCommandLock,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_lookup import (
    BotLookup,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_readiness_reader import (
    BotReadinessReader,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.command import (
    EditBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.edit_bot.handler import (
    EditBotCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.start_bot.command import (
    StartBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore


class StartBotCommandHandler(ICommandHandler[StartBotCommand, BotCommandResult]):
    """Refuses what the readiness lists; otherwise moves the bot to STARTING."""

    def __init__(
        self,
        store: IBotStore,
        runner: IBotRunner,
        lock: BotCommandLock,
        readiness: BotReadinessReader,
        clock: IBotClock,
    ) -> None:
        self._lookup = BotLookup(store)
        self._runner = runner
        self._lock = lock
        self._readiness = readiness
        self._edit = EditBotCommandHandler(store, clock)

    def execute(self, command: StartBotCommand) -> BotCommandResult:
        with self._lock.held():
            found = self._lookup.find(command.bot_id)
            if isinstance(found, BotCommandResult):
                return found
            readiness = self._readiness.read(found.bot, command.config)
            if not readiness.can_start:
                first = readiness.items[0]
                return BotCommandResult.refused(
                    first.refusal, readiness.message(), command.bot_id
                )
            if command.config is not None and dict(command.config) != dict(
                found.bot.definition.config
            ):
                saved = self._edit.execute(
                    EditBotCommand(
                        command.bot_id, found.bot.definition.name, command.config
                    )
                )
                if not saved.accepted:
                    return saved
            return self._runner.start(command.bot_id)
