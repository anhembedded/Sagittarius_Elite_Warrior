"""`EPIC-044C` (ADR 044 D10) - the owner hears once that a waiting Grid entered its range."""

from __future__ import annotations

from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_alert_source import (
    BotAlertSource,
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
    AlertSubject,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_range_entered_event import (
    BotRangeEnteredEvent,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)


def _source() -> tuple[BotAlertSource, RecordingAlertPublisher]:
    published = RecordingAlertPublisher()
    return BotAlertSource(
        Bots(entry("RUNNING")), published, FakeAlertClock()
    ), published


def _entered(orders: int = 8) -> BotRangeEnteredEvent:
    return BotRangeEnteredEvent(BOT, Decimal(101), Decimal(100), Decimal(140), orders)


def test_an_entry_is_one_info_alert_naming_the_price_the_range_and_the_orders() -> None:
    source, published = _source()

    source.on_range_entered(_entered())

    [alert] = published.published
    assert alert.kind is AlertKind.BOT_RANGE_ENTERED
    assert alert.severity is Severity.INFO
    assert "101" in alert.detail and "100-140" in alert.detail
    assert "laid 8 order(s)" in alert.detail
    assert "eth-grid" in alert.title


def test_the_state_changes_of_the_entry_publish_no_second_alert() -> None:
    """The entry crosses AWAITING_RANGE, STARTING and RUNNING: only the event tells."""
    bots = Bots(entry("AWAITING_RANGE"))
    published = RecordingAlertPublisher()
    source = BotAlertSource(bots, published, FakeAlertClock())
    source.seed()

    for state in ("STARTING", "RUNNING"):
        bots.move(state)
        source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    source.on_range_entered(_entered())

    assert [alert.kind for alert in published.published] == [
        AlertKind.BOT_RANGE_ENTERED
    ]


def test_a_halted_bot_resumed_into_the_wait_ends_its_halt_condition() -> None:
    bots = Bots(entry("RUNNING"))
    published = RecordingAlertPublisher()
    source = BotAlertSource(bots, published, FakeAlertClock())
    source.seed()
    bots.move("HALTED")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    published.cleared.clear()

    bots.move("AWAITING_RANGE")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))

    cleared = set(published.cleared)
    assert {_key(AlertKind.BOT_HALTED), _key(AlertKind.BOT_ERROR)} <= cleared
    assert len(published.published) == 1, "only the halt itself was ever told"


def _key(kind: AlertKind) -> str:
    subject = AlertSubject.bot(BOT, "eth-grid", "grid", "spot_mainnet", "ETHUSDT")
    return Alert.condition_key(kind, subject)
