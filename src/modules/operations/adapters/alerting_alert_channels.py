"""Whether a bot's halt reaches a person, as the alerting module answers it
(`EPIC-036G`, decision D5).

`alerting` knows its channels; `operations` only asks, through
`alerting/contracts`, so neither imports the other's insides and `alerting`
depends on no module but `bots`.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alerting_status import (
    IAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)


class AlertingAlertChannels(IAlertChannels):
    def __init__(self, status: IAlertingStatus) -> None:
        self._status = status

    def carries_bot_events(self) -> bool:
        return self._status.carries_bot_events()
