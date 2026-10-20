"""`EPIC-036B` — a failure of the app itself reaches the owner as one `APP_FAILURE` alert."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.system_alert_source import (
    SystemAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_publisher import (
    IAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert import Alert
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import build_rig


def _world() -> tuple[SystemAlertSource, RecordingAlertPublisher, FakeAlertClock]:
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    return SystemAlertSource(published, clock), published, clock


class _BrokenPublisher(IAlertPublisher):
    def publish(self, alert: Alert) -> None:
        raise RuntimeError("the outbox is locked")

    def condition_cleared(self, dedup_key: str, at: datetime) -> None:
        raise RuntimeError("the outbox is locked")


def test_a_failed_task_is_one_critical_app_alert_with_its_summary() -> None:
    source, published, clock = _world()

    source.report_failure(
        "historical-sync",
        "Background task 'historical-sync' (id t1) failed: ValueError: grid drifted",
    )

    [alert] = published.published
    assert alert.kind is AlertKind.APP_FAILURE
    assert alert.severity is Severity.CRITICAL
    assert alert.subject.scope is SubjectScope.APP
    assert "historical-sync" in alert.title
    assert "grid drifted" in alert.detail
    assert alert.at == clock.now()


def test_the_same_failure_twice_shares_one_condition_and_another_source_does_not() -> (
    None
):
    source, published, _ = _world()

    source.report_failure("ws-reconnect", "ConnectionError: dropped")
    source.report_failure("ws-reconnect", "ConnectionError: dropped again")
    source.report_failure("candle-sync", "ValueError: bad candle")

    first, repeat, other = published.published
    assert first.dedup_key == repeat.dedup_key
    assert other.dedup_key != first.dedup_key


def test_a_source_that_cannot_publish_logs_and_never_raises(
    caplog: pytest.LogCaptureFixture,
) -> None:
    source = SystemAlertSource(_BrokenPublisher(), FakeAlertClock())

    with caplog.at_level(logging.WARNING, logger="App.Alerting"):
        source.report_failure("job-a", "boom")

    assert any("job-a" in record.getMessage() for record in caplog.records)


def test_twenty_failing_tasks_of_one_kind_reach_the_channel_once(
    tmp_path: Path,
) -> None:
    rig = build_rig(tmp_path, channel_ids=("phone",))
    source = SystemAlertSource(rig.hub, rig.clock)

    for _ in range(20):
        source.report_failure("ws-reconnect", "ConnectionError: dropped")
    rig.deliver_all()

    assert rig.received_kinds("phone") == [AlertKind.APP_FAILURE]
