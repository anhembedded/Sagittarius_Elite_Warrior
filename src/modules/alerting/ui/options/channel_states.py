"""What each channel's secrets and lane are now, read together on the pool (`EPIC-036D4`)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramChannelState,
)


@dataclass(frozen=True, slots=True)
class ChannelStates:
    discord: DiscordChannelState
    telegram: TelegramChannelState
