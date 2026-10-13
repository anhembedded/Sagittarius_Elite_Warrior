"""`IAlertChannelCatalog` — the channels this run has, by id."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)


class IAlertChannelCatalog(ABC):
    @abstractmethod
    def channel_ids(self) -> tuple[str, ...]:
        """Every channel id, in a stable order (the order composition declared)."""

    @abstractmethod
    def channel(self, channel_id: str) -> IAlertChannel:
        """The channel called `channel_id`.

        @raise KeyError No such channel.
        """
