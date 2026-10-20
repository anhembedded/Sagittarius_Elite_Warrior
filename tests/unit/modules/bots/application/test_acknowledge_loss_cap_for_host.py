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
    LossCapAcknowledgement,
)


class _Cap(ILossCapAcknowledgement):
    def __init__(self, answer: LossCapAcknowledgement) -> None:
        self.answer = answer
        self.acknowledged = 0

    def acknowledge(self) -> LossCapAcknowledgement:
        self.acknowledged += 1
        return self.answer


def test_acknowledging_a_tripped_cap_is_accepted() -> None:
    cap = _Cap(LossCapAcknowledgement.ACKNOWLEDGED)

    result = AcknowledgeLossCapForHostCommandHandler(cap).execute(
        AcknowledgeLossCapForHostCommand()
    )

    assert result.accepted and result.bot_id == LOSS_CAP_SUBJECT
    assert cap.acknowledged == 1


def test_acknowledging_a_cap_that_is_not_tripped_is_refused_in_words() -> None:
    result = AcknowledgeLossCapForHostCommandHandler(
        _Cap(LossCapAcknowledgement.NOT_TRIPPED)
    ).execute(AcknowledgeLossCapForHostCommand())

    assert not result.accepted and result.refusal is BotRefusal.LOSS_CAP_NOT_TRIPPED
    assert "not tripped" in result.message


def test_acknowledging_while_the_loss_is_still_at_the_figure_is_refused_with_the_way_out() -> (
    None
):
    result = AcknowledgeLossCapForHostCommandHandler(
        _Cap(LossCapAcknowledgement.STILL_AT_FIGURE)
    ).execute(AcknowledgeLossCapForHostCommand())

    assert not result.accepted
    assert result.refusal is BotRefusal.LOSS_CAP_STILL_AT_FIGURE
    assert "raise bots.account_loss_cap" in result.message
