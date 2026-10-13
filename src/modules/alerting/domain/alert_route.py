"""One cell of the Options matrix."""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness


@dataclass(frozen=True, slots=True)
class AlertRoute:
    """How `group` sounds on `channel_id`."""

    group: AlertGroup
    channel_id: str
    loudness: Loudness
