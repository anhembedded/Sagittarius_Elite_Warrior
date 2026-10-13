"""A bounded queue per channel: INFO goes before WARNING, CRITICAL never (design §7)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import replace

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity


class DeliveryAdmission:
    def __init__(self, outbox: IOutbox, policy: DeliveryPolicy) -> None:
        self._outbox = outbox
        self._policy = policy

    def admit(
        self, targets: Iterable[DeliveryTarget], severity: Severity
    ) -> tuple[DeliveryTarget, ...]:
        """The targets with room made for them.

        A full queue sheds the oldest delivery of the lowest severity *below*
        the newcomer. With nothing below, a newcomer under CRITICAL is itself
        recorded as `DROPPED`; a CRITICAL is admitted beyond the bound, because
        CRITICAL is never dropped.
        """
        return tuple(self._admit_one(target, severity) for target in targets)

    def _admit_one(self, target: DeliveryTarget, severity: Severity) -> DeliveryTarget:
        if self._outbox.pending_count(target.channel_id) < self._policy.capacity:
            return target
        if self._outbox.shed_lowest(target.channel_id, severity):
            return target
        if severity is Severity.CRITICAL:
            return target
        return replace(target, state=DeliveryState.DROPPED)
