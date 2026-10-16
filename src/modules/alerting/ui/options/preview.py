"""Preview of the Alerts page of Tools → Options (`EPIC-036D1`).

`scripts/preview-qml.ps1 alerts_options` (`--list` names every preview) renders the
page headless with no presenter: the view over a view model set to the states the
owner meets — nothing saved, a saved webhook waiting for a restart, a refused test.
The URL below is a made-up one; nothing here reads a secret store.
"""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from Sagittarius_Elite_Warrior.src.modules.alerting.application.discord_webhook_setup import (
    DiscordChannelState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options import alerts_words
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view import (
    AlertsSettingsView,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.ui.options.alerts_settings_view_model import (
    AlertsSettingsViewModel,
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
    sentence, is_error = alerts_words.send_test_words(())
    view_model.set_status(sentence, is_error)
    view = AlertsSettingsView()
    view.set_view_model(view_model)
    return view
