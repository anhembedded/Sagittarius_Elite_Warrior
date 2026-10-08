"""`EPIC-035H` — the runner of a copy of the app that is read-only.

The runner is the one door from a command to a running bot. A Start is answered
with a named refusal, as every other refused Start is, before its preconditions
claim a lease or register a budget; the other commands carry on a bot that does
not run here, so they are refused too, with the instance's own reason.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.errors import ReadOnlyInstanceError
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_executor import (
    BaseHandling,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_runner import IBotRunner


class ReadOnlyBotRunner(IBotRunner):
    """Starts and commands no bot."""

    def __init__(self, inner: IBotRunner, reason: str) -> None:
        self._inner = inner
        self._reason = reason

    def start(self, bot_id: str) -> BotCommandResult:
        return BotCommandResult.refused(
            BotRefusal.READ_ONLY_INSTANCE, self._reason, bot_id
        )

    def pause(self, bot_id: str) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def resume(self, bot_id: str) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def stop(self, bot_id: str, base: BaseHandling) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def confirm_resume(self, bot_id: str) -> None:
        raise ReadOnlyInstanceError(self._reason)

    def has_resume_proposal(self, bot_id: str) -> bool:
        raise ReadOnlyInstanceError(self._reason)
