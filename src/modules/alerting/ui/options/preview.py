"""Preview of the Alerts page of Tools → Options (`EPIC-036D1`).

`scripts/preview-qml.ps1 alerts_options` (`--list` names every preview) renders the
page headless with no presenter: the view over a view model set to the states the
owner meets — nothing saved, a saved webhook waiting for a restart, a refused test; this one shows the last two, with three bots set to each of the three choices (`BOT-191`).
The URL below is a made-up one; nothing here reads a secret store.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.send_test_message import (
    ChannelTestOutcome,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view import (
    AlertsSettingsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
    BotModeRow,
)

#: `scripts/preview_qml.py` keys a preview by its parent directory name, `options`,
#: which says nothing across modules.
PREVIEW_KEY = "alerts_options"


def build_preview() -> QWidget:
    """The page with a webhook saved this session and the lane not started yet: the
    state that needs the restart sentence."""
    state = DiscordChannelState(stored=True, usable=True, hint="w9Kp", running=False)
    view_model = AlertsSettingsViewModel()
    view_model.set_channel(
        alerts_words.channel_line(state),
        alerts_words.saved_line(state),
        can_remove=state.stored,
        can_test=state.usable,
    )
    refused = ChannelTestOutcome(
        "discord",
        DeliveryResult.refused("Discord refused the webhook message (404)"),
    )
    sentence, is_error = alerts_words.send_test_words((refused,))
    view_model.set_status(sentence, is_error)
    view_model.set_bot_rows(
        (
            BotModeRow("g3n092", "eth-grid", "on"),
            BotModeRow("k8d114", "sol-grid", "critical_only"),
            BotModeRow("m2x077", "btc-neutral", "off"),
        )
    )
    view = AlertsSettingsView()
    view.set_view_model(view_model)
    return view
