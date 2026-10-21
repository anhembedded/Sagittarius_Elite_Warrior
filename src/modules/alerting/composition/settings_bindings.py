"""What the owner set (`BOT-191`, `EPIC-036D6`): one object serves the hub's reads and the
Options page's edits, so the two cannot disagree. A missing or unreadable file is every default.
Split from `alerting_bindings.py`, which is at the file-size ceiling."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from Sagittarius_Elite_Warrior.src.core.contracts.i_instance_access import (
    IInstanceAccess,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.json_alert_settings import (
    JsonAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_bot_alert_modes import (
    IBotAlertModes,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_quiet_hours_setting import (
    IQuietHoursSetting,
)
from sagittarius_engine.interfaces.i_container import IContainer


def bind_settings(container: IContainer, settings_path: Callable[[], Path]) -> None:
    container.singleton(
        JsonAlertSettings,
        lambda resolver: JsonAlertSettings(
            settings_path(), read_only=resolver.resolve(IInstanceAccess).read_only
        ),
    )
    container.singleton(
        IAlertSettingsSource, lambda resolver: resolver.resolve(JsonAlertSettings)
    )
    container.singleton(
        IBotAlertModes, lambda resolver: resolver.resolve(JsonAlertSettings)
    )
    container.singleton(
        IQuietHoursSetting, lambda resolver: resolver.resolve(JsonAlertSettings)
    )
