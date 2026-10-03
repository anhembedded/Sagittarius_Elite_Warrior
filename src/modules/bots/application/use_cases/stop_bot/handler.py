"""`EPIC-029B` — handler for `StopBotCommand`.

The state change only (to STOPPING). STOPPED comes later, from
`stop_confirmed`, raised by the executor only after a read shows zero open
orders carrying the bot's tag (ADR §3.1); that executor is `EPIC-029E`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_event_runner import (
    BotEventRunner,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.stop_bot.command import (
    StopBotCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_clock import IBotClock
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class StopBotCommandHandler(ICommandHandler[StopBotCommand, BotCommandResult]):
    """Puts `stop` through the lifecycle table and saves the bot as STOPPING."""

    def __init__(self, store: IBotStore, clock: IBotClock) -> None:
        self._runner = BotEventRunner(store, clock)

    def execute(self, command: StopBotCommand) -> BotCommandResult:
        return self._runner.run(command.bot_id, BotLifecycleEvent.STOP)
