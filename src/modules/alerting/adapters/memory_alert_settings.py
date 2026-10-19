"""`IAlertSettingsSource` held in memory.

`EPIC-036A` ships the defaults of N4 and no persistence (`BOT-191` added `JsonAlertSettings` for the
per-bot modes): the Options page
(`EPIC-036D`) brings the store that survives a restart and replaces this class
at its binding. `replace` is this adapter's own, not the port's: only the page
that owns the store edits settings.
"""

from __future__ import annotations

import threading

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_settings_source import (
    IAlertSettingsSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)


class InMemoryAlertSettings(IAlertSettingsSource):
    def __init__(self, settings: AlertSettings | None = None) -> None:
        self._lock = threading.Lock()
        self._settings = settings or AlertSettings()

    def current(self) -> AlertSettings:
        with self._lock:
            return self._settings

    def replace(self, settings: AlertSettings) -> None:
        with self._lock:
            self._settings = settings
