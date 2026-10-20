"""`ILossCapHold` for a test that is not about the loss cap: nothing is ever held (`EPIC-026L`)."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_loss_cap_hold import (
    ILossCapHold,
)


class FreeLossCapHold(ILossCapHold):
    def restart_refusal(self) -> str | None:
        return None
