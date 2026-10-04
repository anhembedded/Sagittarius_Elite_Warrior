"""`EPIC-029B` — handler for `StopBotCommand`.

`EPIC-029E`: checked against the lifecycle table here, carried out by the
bot's executor (`BotCommandGate`, ADR D9). The executor moves the bot to
STOPPING; STOPPED comes only from `stop_confirmed`, after a read shows zero
open orders carrying the bot's tag (ADR §3.1).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.command import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class StopBotCommandHandler(ICommandHandler[StopBotCommand, BotCommandResult]):
    """Refuses `stop` where the table does not declare it; otherwise queues it."""

    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._gate = BotCommandGate(store)
        self._runner = runner

    def execute(self, command: StopBotCommand) -> BotCommandResult:
        return self._gate.run(
            command.bot_id,
            BotLifecycleEvent.STOP,
            lambda bot_id: self._runner.stop(bot_id, command.base),
        )
