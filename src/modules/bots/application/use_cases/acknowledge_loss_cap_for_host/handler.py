"""`EPIC-026L` - the host's "the owner acknowledges the loss cap".

The command is a contract type (`host_bot_requests.py`), as every request the `run` host sends
the bots is; the handler asks the cap to clear itself and answers in the words the bots' other
host commands answer in. Acknowledging a cap that is not tripped is refused, in words, so an
owner who typed it twice, or at the wrong host, learns that nothing changed.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    LOSS_CAP_SUBJECT,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_cqrs import ICommandHandler
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotCommandResult,
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AcknowledgeLossCapForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_acknowledgement import (
    ILossCapAcknowledgement,
)


class AcknowledgeLossCapForHostCommandHandler(
    ICommandHandler[AcknowledgeLossCapForHostCommand, BotCommandResult]
):
    def __init__(self, cap: ILossCapAcknowledgement) -> None:
        self._cap = cap

    def execute(self, command: AcknowledgeLossCapForHostCommand) -> BotCommandResult:
        if self._cap.acknowledge():
            return BotCommandResult.done(LOSS_CAP_SUBJECT)
        return BotCommandResult.refused(
            BotRefusal.LOSS_CAP_NOT_TRIPPED,
            "the account-level loss cap is not tripped; nothing to acknowledge",
            LOSS_CAP_SUBJECT,
        )
