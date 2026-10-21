"""`EPIC-036D5` — Retry failed: failed deliveries inside the expiry go out again, through the
real lane, with the real outbox; only the channel is scripted."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_delivery_requeue import (
    SqliteDeliveryRequeue,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.retry_failed_deliveries import (
    RetryFailedDeliveries,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.delivery_result import (
    DeliveryResult,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    an_alert,
    build_rig,
)


def _use_case(rig) -> RetryFailedDeliveries:  # type: ignore[no-untyped-def]
    return RetryFailedDeliveries(
        SqliteDeliveryRequeue(rig.path), rig.clock, DeliveryPolicy()
    )


def _states(rig) -> list[DeliveryState]:  # type: ignore[no-untyped-def]
    return [d.state for e in rig.outbox.history(10) for d in e.deliveries]


def test_a_refused_delivery_is_sent_after_retry_failed_once_the_channel_works(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.channels["phone"].script.append(DeliveryResult.refused("webhook deleted"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()
    assert _states(rig) == [DeliveryState.FAILED]

    count = _use_case(rig).run()
    rig.deliver_all()

    assert count == 1
    assert _states(rig) == [DeliveryState.SENT]


def test_nothing_is_requeued_when_nothing_failed(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()

    count = _use_case(rig).run()

    assert count == 0
    assert _states(rig) == [DeliveryState.SENT]


def test_a_failure_older_than_the_expiry_is_not_sent_late(tmp_path: Path) -> None:
    rig = build_rig(tmp_path, ("phone",))
    rig.channels["phone"].script.append(DeliveryResult.refused("webhook deleted"))
    rig.hub.publish(an_alert(AlertKind.BOT_HALTED))
    rig.deliver_all()
    rig.clock.advance(DeliveryPolicy().expiry + timedelta(minutes=1))

    count = _use_case(rig).run()

    assert count == 0
    assert _states(rig) == [DeliveryState.FAILED]
