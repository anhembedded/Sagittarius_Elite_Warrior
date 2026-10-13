"""The alert channels there are until `EPIC-036B` routes bot events to one: none."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)


class NoAlertChannels(IAlertChannels):
    """Nothing sends a bot's halt to a person today, so the host says so.

    `EPIC-036B` replaces this binding with an adapter that asks the alerting
    module whether a channel carries bot events.
    """

    def carries_bot_events(self) -> bool:
        return False
