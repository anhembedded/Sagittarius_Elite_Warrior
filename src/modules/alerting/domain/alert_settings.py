"""What the owner configured. Holds no secret: a channel reads its own by name
when it sends (N3)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_route import AlertRoute
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.quiet_hours import QuietHours
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


@dataclass(frozen=True, slots=True)
class AlertSettings:
    """The defaults are N4's: with no route CRITICAL is loud and WARNING and
    INFO are silent, every channel is enabled and no bot is muted."""

    disabled_channels: frozenset[str] = frozenset()
    routes: tuple[AlertRoute, ...] = ()
    bot_modes: Mapping[str, BotAlertMode] = field(default_factory=dict)
    quiet_hours: QuietHours | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "bot_modes", MappingProxyType(dict(self.bot_modes)))

    def loudness_for(
        self, group: AlertGroup, channel_id: str, severity: Severity
    ) -> Loudness:
        """The cell for `group` and `channel_id`, else the default for `severity`."""
        for route in self.routes:
            if route.group is group and route.channel_id == channel_id:
                return route.loudness
        return Loudness.LOUD if severity is Severity.CRITICAL else Loudness.SILENT

    def mode_of(self, bot_id: str) -> BotAlertMode:
        return self.bot_modes.get(bot_id, BotAlertMode.ON)
