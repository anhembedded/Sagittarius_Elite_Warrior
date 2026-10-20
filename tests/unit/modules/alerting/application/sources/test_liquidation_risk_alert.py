"""`EPIC-036B1` — a Futures bot inside its liquidation warning distance reaches the owner once."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_subject import (
    subject_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.liquidation_alert_source import (
    LiquidationAlertSource,
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
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_changed_event import (
    BotChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskLevel
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.application.sources.bot_source_world import (
    BOT,
    Bots,
    entry,
)


def _event(level: RiskLevel) -> BotRiskChangedEvent:
    return BotRiskChangedEvent(
        bot_id=BOT,
        symbol="ETHUSDT",
        level=level,
        reason="The mark price 1900 is 9.50% from the exchange's liquidation price 1720, "
        "inside the warning 10.00%",
        distance=Decimal("0.095"),
        mark_price=Decimal(1900),
        liquidation_price=Decimal(1720),
    )


def _world() -> tuple[LiquidationAlertSource, RecordingAlertPublisher, FakeAlertClock]:
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    return LiquidationAlertSource(Bots(entry()), published, clock), published, clock


def _key() -> str:
    return Alert.condition_key(AlertKind.LIQUIDATION_RISK, subject_of(entry()))


def test_a_warning_level_is_one_warning_alert_about_the_bot_with_the_figures() -> None:
    source, published, _ = _world()

    source.on_risk_changed(_event(RiskLevel.WARN))

    [alert] = published.published
    assert alert.kind is AlertKind.LIQUIDATION_RISK
    assert alert.severity is Severity.WARNING
    assert alert.subject.scope is SubjectScope.BOT
    assert alert.subject.bot_id == BOT
    assert "mark price 1900" in alert.detail
    assert "liquidation price 1720" in alert.detail
    assert "distance 9.50%" in alert.detail


def test_a_second_warning_while_the_first_stands_is_not_told_again() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(hours=2))

    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 1


def test_the_return_to_safe_clears_the_warning_once() -> None:
    source, published, _ = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))

    source.on_risk_changed(_event(RiskLevel.SAFE))
    source.on_risk_changed(_event(RiskLevel.SAFE))

    assert published.cleared == [_key()]


def test_a_safe_reading_that_follows_no_warning_clears_nothing() -> None:
    source, published, _ = _world()

    source.on_risk_changed(_event(RiskLevel.SAFE))

    assert published.cleared == []
    assert published.published == []


def test_a_mark_price_that_crosses_the_line_again_inside_the_cooldown_sends_no_pair() -> (
    None
):
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    source.on_risk_changed(_event(RiskLevel.SAFE))
    clock.advance(timedelta(minutes=5))

    source.on_risk_changed(_event(RiskLevel.WARN))
    source.on_risk_changed(_event(RiskLevel.SAFE))

    assert len(published.published) == 1
    assert published.cleared == [_key()]


def test_the_warning_is_raised_again_after_the_cooldown() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    source.on_risk_changed(_event(RiskLevel.SAFE))
    clock.advance(timedelta(minutes=11))

    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 2


def test_the_critical_level_raises_nothing_of_its_own_because_the_halt_is_the_alert() -> (
    None
):
    source, published, _ = _world()

    source.on_risk_changed(_event(RiskLevel.CRITICAL))
    source.on_risk_changed(_event(RiskLevel.UNKNOWN))

    assert published.published == []


def test_a_bot_that_stops_ends_its_open_warning_and_may_warn_afresh_later() -> None:
    bots = Bots(entry())
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    source = LiquidationAlertSource(bots, published, clock)
    source.on_risk_changed(_event(RiskLevel.WARN))
    bots.move("STOPPED")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    assert _key() in published.cleared

    clock.advance(timedelta(minutes=11))
    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 2


def test_a_removed_bot_ends_its_open_warning() -> None:
    source, published, _ = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))

    source.on_bot_changed(BotChangedEvent(bot_id=BOT, removed=True))

    assert published.cleared == [_key()]


def test_a_bot_that_keeps_running_keeps_its_warning() -> None:
    source, published, _ = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))

    source.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert published.cleared == []
