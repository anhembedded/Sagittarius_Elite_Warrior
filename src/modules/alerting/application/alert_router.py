"""Who hears an alert, and how loudly (design §7, N4, N5, N8)."""

from __future__ import annotations

from collections.abc import Sequence

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import group_of
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.bot_alert_mode import (
    BotAlertMode,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity

#: N8: a phone push that never arrives is a known failure, so CRITICAL asks for
#: a second channel whenever the owner has one.
CRITICAL_CHANNELS = 2


class AlertRouter:
    """Pure: the same alert and settings always route the same way."""

    def route(
        self,
        alert: Alert,
        settings: AlertSettings,
        available: Sequence[str],
        excluded: frozenset[str] = frozenset(),
    ) -> tuple[DeliveryTarget, ...]:
        """The deliveries `alert` earns.

        - a bot set to *Off* sends nothing, *Critical only* drops the rest (N5);
        - a disabled channel, or one in `excluded` (the channel the alert is
          about), is never used, not even for CRITICAL;
        - each remaining channel is a cell of the matrix (`loudness_for`); an
          off cell sends nothing;
        - **N8:** a CRITICAL that fewer than two channels would hear is lifted to
          two, loud, from the enabled channels whose cell was off. The matrix
          cannot remove the cover for a push that never arrives.
        """
        if not self._bot_allows(alert, settings):
            return ()
        usable = [
            channel_id
            for channel_id in available
            if channel_id not in settings.disabled_channels
            and channel_id not in excluded
        ]
        group = group_of(alert.kind)
        chosen: list[DeliveryTarget] = []
        for channel_id in usable:
            loudness = settings.loudness_for(group, channel_id, alert.severity)
            if loudness is not Loudness.OFF:
                chosen.append(DeliveryTarget(channel_id, loudness))
        if alert.severity is Severity.CRITICAL:
            taken = {target.channel_id for target in chosen}
            for channel_id in usable:
                if len(chosen) >= CRITICAL_CHANNELS:
                    break
                if channel_id not in taken:
                    chosen.append(DeliveryTarget(channel_id, Loudness.LOUD))
        return tuple(chosen)

    @staticmethod
    def _bot_allows(alert: Alert, settings: AlertSettings) -> bool:
        if alert.subject.scope is not SubjectScope.BOT:
            return True
        mode = settings.mode_of(alert.subject.bot_id)
        if mode is BotAlertMode.OFF:
            return False
        return mode is BotAlertMode.ON or alert.severity is Severity.CRITICAL
