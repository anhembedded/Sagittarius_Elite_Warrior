"""The SQLite outbox behind `IOutbox` (N2)."""

from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.outbox_records import (
    DeliveryTarget,
    DeliveryUpdate,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import NOW, an_alert


def _outbox(tmp_path: Path) -> SqliteOutbox:
    return SqliteOutbox(tmp_path / "state" / "alerts.sqlite3")


def test_the_file_is_created_with_its_folder(tmp_path: Path) -> None:
    _outbox(tmp_path).close()

    assert (tmp_path / "state" / "alerts.sqlite3").is_file()


def test_an_alert_and_its_deliveries_round_trip(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    alert = an_alert(AlertKind.STOP_LOSS_HIT, reason="low 2415.8")

    alert_id = outbox.enqueue(
        alert,
        (
            DeliveryTarget("phone", Loudness.LOUD),
            DeliveryTarget("backup", Loudness.SILENT),
        ),
        NOW,
    )

    [entry] = outbox.history(10)
    assert entry.record.alert_id == alert_id
    assert entry.record.alert == alert
    assert entry.record.count == 1
    assert [(d.channel_id, d.loudness, d.state) for d in entry.deliveries] == [
        ("phone", Loudness.LOUD, DeliveryState.PENDING),
        ("backup", Loudness.SILENT, DeliveryState.PENDING),
    ]


def test_due_returns_critical_first_then_oldest(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(AlertKind.HEARTBEAT), target, NOW)
    outbox.enqueue(an_alert(AlertKind.RATE_LIMITED), target, NOW)
    outbox.enqueue(an_alert(AlertKind.BOT_HALTED), target, NOW)
    outbox.enqueue(an_alert(AlertKind.BOT_ERROR), target, NOW)

    kinds = [d.alert.kind for d in outbox.due("phone", NOW, 10)]

    assert kinds == [
        AlertKind.BOT_HALTED,
        AlertKind.BOT_ERROR,
        AlertKind.RATE_LIMITED,
        AlertKind.HEARTBEAT,
    ]


def test_a_delivery_is_not_due_before_its_next_attempt(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    outbox.enqueue(an_alert(), (DeliveryTarget("phone", Loudness.LOUD),), NOW)
    [due] = outbox.due("phone", NOW, 10)

    outbox.mark(
        due.delivery.delivery_id,
        DeliveryUpdate(DeliveryState.RETRYING, 1, NOW + timedelta(seconds=60), "later"),
    )

    assert outbox.due("phone", NOW + timedelta(seconds=59), 10) == ()
    assert len(outbox.due("phone", NOW + timedelta(seconds=60), 10)) == 1


def test_due_is_per_channel(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    outbox.enqueue(
        an_alert(),
        (
            DeliveryTarget("phone", Loudness.LOUD),
            DeliveryTarget("backup", Loudness.LOUD),
        ),
        NOW,
    )

    assert len(outbox.due("phone", NOW, 10)) == 1
    assert len(outbox.due("backup", NOW, 10)) == 1
    assert outbox.due("nobody", NOW, 10) == ()


def test_a_finished_delivery_is_no_longer_due(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    outbox.enqueue(an_alert(), (DeliveryTarget("phone", Loudness.LOUD),), NOW)
    [due] = outbox.due("phone", NOW, 10)

    outbox.mark(
        due.delivery.delivery_id, DeliveryUpdate(DeliveryState.SENT, 1, NOW, "")
    )

    assert outbox.due("phone", NOW, 10) == ()


def test_a_repeat_bumps_the_count_and_last_time(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    alert_id = outbox.enqueue(an_alert(), (), NOW)

    outbox.bump(alert_id, NOW + timedelta(seconds=5))
    outbox.bump(alert_id, NOW + timedelta(seconds=9))

    [entry] = outbox.history(10)
    assert entry.record.count == 3
    assert entry.record.last_at == NOW + timedelta(seconds=9)


def test_history_is_newest_first_and_limited(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    for number in range(5):
        outbox.enqueue(
            an_alert(reason=str(number)), (), NOW + timedelta(seconds=number)
        )

    reasons = [e.record.alert.dedup_key.rsplit(":", 1)[-1] for e in outbox.history(3)]

    assert reasons == ["4", "3", "2"]


def test_expiry_marks_open_deliveries_of_old_alerts_only(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(reason="old"), target, NOW)
    outbox.enqueue(an_alert(reason="new", at=NOW + timedelta(hours=2)), target, NOW)

    expired = outbox.expire_before(NOW + timedelta(hours=1))

    assert expired == 1
    [due] = outbox.due("phone", NOW + timedelta(hours=3), 10)
    assert due.alert.dedup_key.endswith("new")


def test_shedding_removes_the_oldest_of_the_lowest_severity_below_the_incoming(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(AlertKind.HEARTBEAT, reason="first"), target, NOW)
    outbox.enqueue(an_alert(AlertKind.HEARTBEAT, reason="second"), target, NOW)
    outbox.enqueue(an_alert(AlertKind.RATE_LIMITED), target, NOW)

    assert outbox.pending_count("phone") == 3
    assert outbox.shed_lowest("phone", Severity.CRITICAL) is True
    assert outbox.pending_count("phone") == 2
    assert outbox.shed_lowest("phone", Severity.INFO) is False  # nothing below INFO

    keys = sorted(d.alert.dedup_key for d in outbox.due("phone", NOW, 10))
    assert not any(key.endswith("first") for key in keys)


def test_shedding_a_surplus_keeps_the_newest_of_one_kind_on_one_channel(
    tmp_path: Path,
) -> None:
    """`BOT-189`: only the oldest fill messages past the bound go; other kinds and other channels
    are untouched."""
    outbox = _outbox(tmp_path)
    phone = (DeliveryTarget("phone", Loudness.SILENT),)
    backup = (DeliveryTarget("backup", Loudness.SILENT),)
    for number in range(4):
        outbox.enqueue(
            an_alert(AlertKind.ORDER_FILLED, reason=f"o-{number}"), phone, NOW
        )
    outbox.enqueue(an_alert(AlertKind.ORDER_FILLED, reason="elsewhere"), backup, NOW)
    outbox.enqueue(an_alert(AlertKind.RATE_LIMITED), phone, NOW)

    dropped = outbox.shed_surplus("phone", AlertKind.ORDER_FILLED, 2)

    assert dropped == 2
    kept = sorted(d.alert.dedup_key for d in outbox.due("phone", NOW, 10))
    assert [key.rsplit(":", 1)[1] for key in kept if "ORDER_FILLED" in key] == [
        "o-2",
        "o-3",
    ]
    assert any("RATE_LIMITED" in key for key in kept)
    assert outbox.pending_count("backup") == 1
    assert outbox.shed_surplus("phone", AlertKind.ORDER_FILLED, 2) == 0


def test_the_backlog_counts_open_deliveries_and_ages_the_oldest(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    assert outbox.backlog(NOW).depth == 0
    assert outbox.backlog(NOW).oldest_age is None

    outbox.enqueue(an_alert(), (DeliveryTarget("phone", Loudness.LOUD),), NOW)
    outbox.enqueue(
        an_alert(reason="b"),
        (DeliveryTarget("phone", Loudness.LOUD),),
        NOW + timedelta(minutes=1),
    )

    backlog = outbox.backlog(NOW + timedelta(minutes=10))
    assert backlog.depth == 2
    assert backlog.oldest_age == timedelta(minutes=10)


def test_finished_alerts_are_purged_after_the_retention_and_open_ones_kept(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(reason="done"), target, NOW)
    outbox.enqueue(an_alert(reason="open"), target, NOW)
    [first, _second] = outbox.due("phone", NOW, 10)
    outbox.mark(
        first.delivery.delivery_id, DeliveryUpdate(DeliveryState.SENT, 1, NOW, "")
    )

    removed = outbox.purge_finished_before(NOW + timedelta(days=1))

    assert removed == 1
    [entry] = outbox.history(10)
    assert entry.record.alert.dedup_key.endswith("open")


def test_channels_of_an_alert_lists_every_channel_holding_it(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    alert_id = outbox.enqueue(
        an_alert(), (DeliveryTarget("phone", Loudness.LOUD),), NOW
    )
    outbox.add_delivery(alert_id, DeliveryTarget("pager", Loudness.LOUD), NOW)

    assert outbox.channels_of(alert_id) == frozenset({"phone", "pager"})


def test_the_retry_horizon_is_the_latest_wait_among_a_channels_retrying_rows(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    target = (DeliveryTarget("phone", Loudness.LOUD),)
    outbox.enqueue(an_alert(reason="a"), target, NOW)
    outbox.enqueue(an_alert(reason="b"), target, NOW)
    outbox.enqueue(
        an_alert(reason="other"), (DeliveryTarget("backup", Loudness.LOUD),), NOW
    )
    first, second = outbox.due("phone", NOW, 10)
    assert outbox.retry_horizon("phone") is None

    outbox.mark(
        first.delivery.delivery_id,
        DeliveryUpdate(DeliveryState.RETRYING, 0, NOW + timedelta(minutes=3), "x"),
    )
    outbox.mark(
        second.delivery.delivery_id,
        DeliveryUpdate(DeliveryState.RETRYING, 0, NOW + timedelta(minutes=10), "x"),
    )

    assert outbox.retry_horizon("phone") == NOW + timedelta(minutes=10)
    assert outbox.retry_horizon("backup") is None


def test_the_newest_alert_of_a_kind_is_found_without_reading_the_history(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    older = an_alert(AlertKind.HEARTBEAT, at=NOW, reason="a")
    newer = an_alert(AlertKind.HEARTBEAT, at=NOW + timedelta(hours=6), reason="b")
    for alert in (
        older,
        an_alert(AlertKind.BOT_HALTED, at=NOW + timedelta(hours=9)),
        newer,
    ):
        outbox.enqueue(alert, (), alert.at)

    assert outbox.latest_alert_at(AlertKind.HEARTBEAT) == newer.at
    assert outbox.latest_alert_at(AlertKind.DAILY_SUMMARY) is None


def test_an_alert_is_found_by_its_dedup_key(tmp_path: Path) -> None:
    outbox = _outbox(tmp_path)
    alert = an_alert(AlertKind.DAILY_SUMMARY, reason="daily-2026-10-20")
    outbox.enqueue(alert, (), NOW)

    assert outbox.has_alert_keyed(alert.dedup_key)
    assert not outbox.has_alert_keyed(alert.dedup_key + "x")


def test_counts_since_add_up_every_repeat_of_an_alert_and_skip_older_ones(
    tmp_path: Path,
) -> None:
    outbox = _outbox(tmp_path)
    halted = an_alert(AlertKind.BOT_HALTED, at=NOW)
    alert_id = outbox.enqueue(halted, (), NOW)
    outbox.bump(alert_id, NOW + timedelta(minutes=1))
    outbox.bump(alert_id, NOW + timedelta(minutes=2))
    old = an_alert(AlertKind.RATE_LIMITED, at=NOW - timedelta(days=2), reason="o")
    outbox.enqueue(old, (), old.at)
    for number in range(600):
        fill = an_alert(AlertKind.ORDER_FILLED, at=NOW, reason=str(number))
        outbox.enqueue(fill, (), NOW)

    counts = outbox.alert_counts_since(NOW - timedelta(hours=24))

    assert counts[AlertKind.BOT_HALTED] == 3
    assert counts[AlertKind.ORDER_FILLED] == 600
    assert AlertKind.RATE_LIMITED not in counts
