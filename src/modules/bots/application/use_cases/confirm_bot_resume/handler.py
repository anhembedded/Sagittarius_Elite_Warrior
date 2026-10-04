"""`EPIC-029E` — handler for `ConfirmBotResumeCommand`.

A resume from HALTED proposes a new plan and places nothing (ADR D13); this is
the user's confirmation of it (O2). Checked against the table here (`resume`
from HALTED), carried out by the bot's executor, which lays the proposal it
holds. With no proposal held (no Resume since the halt, or the app restarted)
the confirmation is refused here, so the screen never reports a confirmation
that lays nothing (PR #333 review).
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
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleEvent,
)


class ConfirmBotResumeCommandHandler(
    ICommandHandler[ConfirmBotResumeCommand, BotCommandResult]
):
    """Refuses unless the bot can resume and a proposal awaits; otherwise
    queues the confirmation."""

    def __init__(self, store: IBotStore, runner: IBotRunner) -> None:
        self._gate = BotCommandGate(store)
        self._runner = runner

    def execute(self, command: ConfirmBotResumeCommand) -> BotCommandResult:
        bot_id = command.bot_id
        refusal = self._gate.refusal(bot_id, BotLifecycleEvent.RESUME)
        if refusal is not None:
            return refusal
        if not self._runner.has_resume_proposal(bot_id):
            return BotCommandResult.refused(
                BotRefusal.NO_RESUME_PROPOSAL,
                "There is no resume proposal to confirm: press Resume first, "
                "check the proposed ladder, then confirm.",
                bot_id,
            )
        self._runner.confirm_resume(bot_id)
        return BotCommandResult.done(bot_id)
