"""`EPIC-036B1` — a Futures bot inside its liquidation warning distance reaches the owner once."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.bot_subject import (
    subject_of,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.liquidation_alert_source import (
    _JUDGED as JUDGED_STATES,
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
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    PRICE_STALENESS_HALTS,
)
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


def test_a_second_warning_inside_the_cooldown_is_not_told_again() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=5))

    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 1


def test_a_warning_still_standing_after_the_cooldown_is_told_again() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=11))

    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 2


def test_the_return_to_safe_after_the_cooldown_clears_the_warning_once() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=11))

    source.on_risk_changed(_event(RiskLevel.SAFE))
    source.on_risk_changed(_event(RiskLevel.SAFE))

    assert published.cleared == [_key()]


def test_a_safe_reading_that_follows_no_warning_clears_nothing() -> None:
    source, published, _ = _world()

    source.on_risk_changed(_event(RiskLevel.SAFE))

    assert published.cleared == []
    assert published.published == []


def test_a_return_to_safe_inside_the_cooldown_sends_no_recovered_that_a_recross_would_falsify() -> (
    None
):
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=2))

    source.on_risk_changed(_event(RiskLevel.SAFE))
    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 1
    assert published.cleared == []


def test_the_critical_level_raises_nothing_of_its_own_because_the_halt_is_the_alert() -> (
    None
):
    source, published, _ = _world()

    source.on_risk_changed(_event(RiskLevel.CRITICAL))
    source.on_risk_changed(_event(RiskLevel.UNKNOWN))

    assert published.published == []


def test_a_bot_that_stops_ends_its_open_warning_with_recovered() -> None:
    bots = Bots(entry())
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    source = LiquidationAlertSource(bots, published, clock)
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=11))

    bots.move("STOPPED")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert published.cleared == [_key()]


def test_a_halted_and_resumed_bot_warns_again_at_its_next_approach() -> None:
    """Review of PR #613: the guard drops to SAFE without an event when the bot halts, so the
    warning is forgotten there, not left open to hold back the next one."""
    bots = Bots(entry())
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    source = LiquidationAlertSource(bots, published, clock)
    source.on_risk_changed(_event(RiskLevel.WARN))

    bots.move("HALTED")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    bots.move("RUNNING")
    source.on_bot_changed(BotChangedEvent(bot_id=BOT))
    clock.advance(timedelta(minutes=1))
    source.on_risk_changed(_event(RiskLevel.WARN))

    assert len(published.published) == 2
    assert published.cleared == []


def test_a_removed_bot_ends_its_open_warning() -> None:
    source, published, clock = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))
    clock.advance(timedelta(minutes=11))

    source.on_bot_changed(BotChangedEvent(bot_id=BOT, removed=True))

    assert published.cleared == [_key()]


def test_a_bot_that_keeps_running_keeps_its_warning() -> None:
    source, published, _ = _world()
    source.on_risk_changed(_event(RiskLevel.WARN))

    source.on_bot_changed(BotChangedEvent(bot_id=BOT))

    assert published.cleared == []


def test_a_write_while_no_warning_is_open_reads_no_status() -> None:
    class _Refusing(Bots):
        def dispatch(
            self, handler_class: type, input_dto: object | None = None
        ) -> object:
            raise AssertionError("the store was read")

    source = LiquidationAlertSource(
        _Refusing(entry()), RecordingAlertPublisher(), FakeAlertClock()
    )

    source.on_bot_changed(BotChangedEvent(bot_id=BOT))


def test_the_states_the_source_treats_as_judged_are_the_guards_own() -> None:
    """The guard resets silently outside `PRICE_STALENESS_HALTS`; the source spells the set by name."""
    assert {state.name for state in PRICE_STALENESS_HALTS} == JUDGED_STATES
