"""`EPIC-026L` — a tripped account-level loss cap reaches the owner as one CRITICAL alert about the app."""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    BotAlertSource,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.recording_alert_publisher import (
    RecordingAlertPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_subject import (
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.account_loss_cap_tripped_event import (
    AccountLossCapTrippedEvent,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    Bots,
)


def _event(reason: str = "loss_reached") -> AccountLossCapTrippedEvent:
    return AccountLossCapTrippedEvent(
        reason=reason,
        figure="500 USDT",
        loss="512.3",
        detail="the day's loss 512.3 USDT reached the cap of 500 USDT",
        bots_stopped=3,
    )


def test_a_trip_is_one_critical_alert_about_the_whole_app() -> None:
    published = RecordingAlertPublisher()
    source = BotAlertSource(Bots(), published, FakeAlertClock())

    source.on_account_loss_cap_tripped(_event())

    [alert] = published.published
    assert alert.kind is AlertKind.ACCOUNT_LOSS_CAP_TRIPPED
    assert alert.severity is Severity.CRITICAL
    assert alert.subject.scope is SubjectScope.APP


def test_the_alert_tells_the_figure_the_loss_the_count_and_how_to_acknowledge() -> None:
    published = RecordingAlertPublisher()
    source = BotAlertSource(Bots(), published, FakeAlertClock())

    source.on_account_loss_cap_tripped(_event())

    [alert] = published.published
    for fact in ("500 USDT", "512.3", "3 bot(s)", "loss-cap-ack"):
        assert fact in alert.detail


def test_two_trips_for_different_reasons_are_different_conditions() -> None:
    published = RecordingAlertPublisher()
    source = BotAlertSource(Bots(), published, FakeAlertClock())

    source.on_account_loss_cap_tripped(_event("loss_reached"))
    source.on_account_loss_cap_tripped(_event("not_judgeable"))

    first, second = published.published
    assert first.dedup_key != second.dedup_key
