"""`EPIC-036D5` — the Retry failed write on the outbox file, through `SqliteOutbox` as the
writer that stored the alerts."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_delivery_requeue import (
    SqliteDeliveryRequeue,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
    DeliveryUpdate,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import NOW, an_alert


def _outbox(tmp_path: Path) -> SqliteOutbox:
    return SqliteOutbox(tmp_path / "state" / "alerts.sqlite3")


def _requeue(tmp_path: Path) -> SqliteDeliveryRequeue:
    return SqliteDeliveryRequeue(tmp_path / "state" / "alerts.sqlite3")


def _fail(outbox: SqliteOutbox, delivery_id: int) -> None:
    outbox.mark(
        delivery_id,
        DeliveryUpdate(DeliveryState.FAILED, 3, NOW, "refused"),
    )


def test_requeue_failed_puts_a_failed_delivery_back_due_now_with_fresh_attempts(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    outbox.enqueue(an_alert(), (DeliveryTarget("phone", Loudness.LOUD),), NOW)
    [due] = outbox.due("phone", NOW, 10)
    _fail(outbox, due.delivery.delivery_id)
    later = NOW + timedelta(minutes=5)

    count = _requeue(tmp_path).requeue_failed(NOW - timedelta(hours=1), later)

    assert count == 1
    [again] = outbox.due("phone", later, 10)
    assert again.delivery.state is DeliveryState.PENDING
    assert again.delivery.attempts == 0


def test_requeue_failed_leaves_sent_expired_and_older_than_the_cutoff_alone(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(reason="old", at=NOW - timedelta(days=2)), target, NOW)
    outbox.enqueue(an_alert(reason="sent"), target, NOW)
    outbox.enqueue(an_alert(reason="expired"), target, NOW)
    ids = {
        d.alert.dedup_key.rsplit(":", 1)[-1]: d.delivery.delivery_id
        for d in outbox.due("phone", NOW, 10)
    }
    _fail(outbox, ids["old"])
    outbox.mark(ids["sent"], DeliveryUpdate(DeliveryState.SENT, 1, NOW, ""))
    outbox.mark(ids["expired"], DeliveryUpdate(DeliveryState.EXPIRED, 0, NOW, "late"))

    count = _requeue(tmp_path).requeue_failed(NOW - timedelta(hours=24), NOW)

    assert count == 0
    states = {d.state for entry in outbox.history(10) for d in entry.deliveries}
    assert states == {DeliveryState.FAILED, DeliveryState.SENT, DeliveryState.EXPIRED}
