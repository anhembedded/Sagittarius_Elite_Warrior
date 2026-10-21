"""What each channel's secrets and lane are now, read together on the pool (`EPIC-036D4`), and how
the page shows them (`show_channel_states`, out of the presenter at the file-size ceiling)."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.telegram_credentials_setup import (
    TelegramChannelState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
)


@dataclass(frozen=True, slots=True)
class ChannelStates:
    discord: DiscordChannelState
    telegram: TelegramChannelState


def show_channel_states(
    view_model: AlertsSettingsViewModel, states: ChannelStates
) -> None:
    """Puts what each channel is now on the page: its line, what is saved, and whether Remove and
    Send test can be used."""
    discord, telegram = states.discord, states.telegram
    view_model.set_channel(
        alerts_words.channel_line(discord),
        alerts_words.saved_line(discord),
        can_remove=discord.stored,
        can_test=discord.usable or telegram.usable,
    )
    view_model.telegram.set_channel(
        alerts_words.telegram_channel_line(telegram),
        alerts_words.telegram_saved_line(telegram),
        can_remove=telegram.stored,
    )
