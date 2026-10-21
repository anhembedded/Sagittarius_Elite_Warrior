"""The heartbeat service's test world: one policy, a service over the rig, the clock helpers."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta

from Sagittarius_Elite_Warrior.src.core.contracts.i_command_dispatcher import (
    ICommandDispatcher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.heartbeat_service import (
    HeartbeatService,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    HeartbeatPolicy,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import NOW, Rig

EVERY = timedelta(hours=6)
POLICY = HeartbeatPolicy(heartbeat_every=EVERY, summary_at=time(1, 0))


def service_of(rig: Rig, bots: ICommandDispatcher) -> HeartbeatService:
    return HeartbeatService(bots, rig.hub, rig.outbox, rig.clock, rig.settings, POLICY)


def beats_of(rig: Rig, kind: AlertKind = AlertKind.HEARTBEAT) -> list[str]:
    return [
        e.record.alert.detail
        for e in rig.outbox.history(500)
        if e.record.alert.kind is kind
    ]


def at(hour: int, minute: int = 0, day_offset: int = 0) -> datetime:
    return datetime(NOW.year, NOW.month, NOW.day, hour, minute, tzinfo=UTC) + timedelta(
        days=day_offset
    )


def start_at(rig: Rig, when: datetime) -> None:
    rig.clock.advance(when - rig.clock.now())
