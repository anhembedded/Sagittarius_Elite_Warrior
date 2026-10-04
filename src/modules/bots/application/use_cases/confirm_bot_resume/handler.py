"""`EPIC-029E` — handler for `ConfirmBotResumeCommand`.

A resume from HALTED proposes a new plan and places nothing (ADR D13); this is
the user's confirmation of it (O2). Checked against the table here (`resume`
from HALTED), carried out by the bot's executor, which lays the proposal it
holds — or does nothing when it holds none.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.application.services.bot_command_gate import (
    BotCommandGate,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.confirm_bot_resume.command import (
    ConfirmBotResumeCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class ConfirmBotResumeCommandHandler(
    ICommandHandler[ConfirmBotResumeCommand, BotCommandResult]
):
    """Refuses unless the bot can resume; otherwise queues the confirmation."""

    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._gate = BotCommandGate(store)
        self._runner = runner

    def execute(self, command: ConfirmBotResumeCommand) -> BotCommandResult:
        return self._gate.run(
            command.bot_id, BotLifecycleEvent.RESUME, self._runner.confirm_resume
        )
