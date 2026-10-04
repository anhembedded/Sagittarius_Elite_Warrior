"""`EPIC-029B` — handler for `PauseBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.pause_bot.command import (
    PauseBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class PauseBotCommandHandler(ICommandHandler[PauseBotCommand, BotCommandResult]):
    """Refuses `pause` where the table does not declare it; otherwise queues it."""

    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._gate = BotCommandGate(store)
        self._runner = runner

    def execute(self, command: PauseBotCommand) -> BotCommandResult:
        return self._gate.run(
            command.bot_id, BotLifecycleEvent.PAUSE, self._runner.pause
        )
