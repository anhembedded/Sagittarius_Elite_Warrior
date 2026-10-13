"""`IAlertSettingsSource` — where the hub reads what the owner configured."""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)


class IAlertSettingsSource(ABC):
    @abstractmethod
    def current(self) -> AlertSettings:
        """The settings now. Read for every alert, so an edit applies to the
        next one without a restart."""
