"""`EPIC-045F` (ADR 045 D7) - the owner hears that the host left a planned mainnet bot unstarted."""

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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_catalog import (
    KIND_PROFILES,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_group import AlertGroup
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.planned_bot_not_started_event import (
    PlannedBotNotStartedEvent,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)


def test_a_skipped_bot_is_one_warning_that_names_the_command_that_starts_it() -> None:
    published = RecordingAlertPublisher()
    source = BotAlertSource(Bots(entry("STOPPED")), published, FakeAlertClock())

    source.on_planned_bot_not_started(
        PlannedBotNotStartedEvent(BOT, "spot_mainnet", "the venue was not confirmed.")
    )

    [alert] = published.published
    assert alert.kind is AlertKind.PLANNED_BOT_NOT_STARTED
    assert alert.severity is Severity.WARNING
    assert f"`bot start {BOT} --confirm-venue spot_mainnet`" in alert.detail
    assert "other bots of the plan were started" in alert.detail
    assert "eth-grid" in alert.title


def test_the_kind_is_a_bot_event_so_it_follows_the_bot_alert_routing() -> None:
    profile = KIND_PROFILES[AlertKind.PLANNED_BOT_NOT_STARTED]

    assert profile.group is AlertGroup.BOT_EVENTS
    assert profile.severity is Severity.WARNING
