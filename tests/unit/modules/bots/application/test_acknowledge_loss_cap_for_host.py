"""`EPIC-026L` — the host's acknowledgement answers in the bots' words and clears nothing it should not."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    LOSS_CAP_SUBJECT,
)
from Sagittarius_Elite_Warrior.src.modules.bots.application.use_cases.acknowledge_loss_cap_for_host import (
    AcknowledgeLossCapForHostCommandHandler,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.bot_command_result import (
    BotRefusal,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_bot_requests import (
    AcknowledgeLossCapForHostCommand,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_acknowledgement import (
    ILossCapAcknowledgement,
)


class _Cap(ILossCapAcknowledgement):
    def __init__(self, tripped: bool) -> None:
        self.tripped = tripped
        self.acknowledged = 0

    def acknowledge(self) -> bool:
        self.acknowledged += 1
        was, self.tripped = self.tripped, False
        return was


def test_acknowledging_a_tripped_cap_is_accepted() -> None:
    cap = _Cap(tripped=True)

    result = AcknowledgeLossCapForHostCommandHandler(cap).execute(
        AcknowledgeLossCapForHostCommand()
    )

    assert result.accepted and result.bot_id == LOSS_CAP_SUBJECT
    assert cap.acknowledged == 1


def test_acknowledging_a_cap_that_is_not_tripped_is_refused_in_words() -> None:
    result = AcknowledgeLossCapForHostCommandHandler(_Cap(tripped=False)).execute(
        AcknowledgeLossCapForHostCommand()
    )

    assert not result.accepted and result.refusal is BotRefusal.LOSS_CAP_NOT_TRIPPED
    assert "not tripped" in result.message
