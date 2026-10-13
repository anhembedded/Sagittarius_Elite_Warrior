"""`IAlertChannelCatalog` over the channels composition declared."""

from __future__ import annotations

from collections.abc import Mapping

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)


class RegisteredChannelCatalog(IAlertChannelCatalog):
    """Fixed for the life of the run; the order is the mapping's."""

    def __init__(self, channels: Mapping[str, IAlertChannel]) -> None:
        self._channels = dict(channels)

    def channel_ids(self) -> tuple[str, ...]:
        return tuple(self._channels)

    def channel(self, channel_id: str) -> IAlertChannel:
        return self._channels[channel_id]
