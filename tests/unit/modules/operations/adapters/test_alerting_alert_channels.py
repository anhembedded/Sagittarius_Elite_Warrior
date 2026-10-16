"""`EPIC-036G` (D5) — the host's question is answered by the alerting module."""

from __future__ import annotations

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alerting_status import (
    IAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.adapters.alerting_alert_channels import (
    AlertingAlertChannels,
)


class _Status(IAlertingStatus):
    def __init__(self, answer: bool) -> None:
        self.answer = answer

    def carries_bot_events(self) -> bool:
        return self.answer


@pytest.mark.parametrize("answer", [True, False])
def test_the_answer_is_alertings(answer: bool) -> None:
    assert AlertingAlertChannels(_Status(answer)).carries_bot_events() is answer
