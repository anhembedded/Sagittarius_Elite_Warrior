"""`EPIC-029B` — handler for `ResumeBotCommand`.

The state change only; the executor that acts on it arrives in `EPIC-029E`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_event_runner import (
    BotEventRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.resume_bot.command import (
    ResumeBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class ResumeBotCommandHandler(ICommandHandler[ResumeBotCommand, BotCommandResult]):
    """Puts `resume` through the lifecycle table and saves the bot."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._runner = BotEventRunner(store, clock)

    def execute(self, command: ResumeBotCommand) -> BotCommandResult:
        return self._runner.run(command.bot_id, BotLifecycleEvent.RESUME)
