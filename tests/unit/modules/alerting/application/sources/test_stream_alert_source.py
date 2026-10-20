"""`EPIC-036B1` — a venue's user-data stream that stays down reaches the owner once."""

from __future__ import annotations

from datetime import timedelta

from Sagittarius_Elite_Warrior.src.modules.alerting.application.sources.stream_alert_source import (
    StreamAlertSource,
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
    SubjectScope,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.severity import Severity
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

VENUE = TradingVenue.FUTURES_MAINNET


def _world() -> tuple[StreamAlertSource, RecordingAlertPublisher, FakeAlertClock]:
    published = RecordingAlertPublisher()
    clock = FakeAlertClock()
    return StreamAlertSource(published, clock), published, clock


def _down(
    clock: FakeAlertClock,
    down_for: timedelta,
    attempt: int = 3,
    venue: TradingVenue = VENUE,
) -> UserStreamHealthEvent:
    return UserStreamHealthEvent(
        state=UserStreamState.RECONNECTING,
        since=clock.now() - down_for,
        attempt=attempt,
        venue=venue,
    )


def _connected(clock: FakeAlertClock) -> UserStreamHealthEvent:
    return UserStreamHealthEvent(
        state=UserStreamState.CONNECTED, since=clock.now(), venue=VENUE
    )


def _key() -> str:
    return Alert.condition_key(
        AlertKind.USER_STREAM_DOWN, AlertSubject.venue_wide(VENUE.value)
    )


def test_an_outage_past_the_grace_is_one_alert_about_the_venue() -> None:
    source, published, clock = _world()

    source.on_user_stream_health(_down(clock, timedelta(seconds=75)))

    [alert] = published.published
    assert alert.kind is AlertKind.USER_STREAM_DOWN
    assert alert.severity is Severity.CRITICAL
    assert alert.subject.scope is SubjectScope.VENUE
    assert alert.subject.venue == VENUE.value
    assert "Futures Mainnet" in alert.detail
    assert "75 s" in alert.detail


def test_a_reconnect_inside_the_grace_is_silent() -> None:
    source, published, clock = _world()

    source.on_user_stream_health(_down(clock, timedelta(seconds=5), attempt=1))
    source.on_user_stream_health(_connected(clock))

    assert published.published == []
    assert published.cleared == []


def test_the_retries_of_one_outage_are_told_once() -> None:
    source, published, clock = _world()
    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))
    clock.advance(timedelta(seconds=60))

    source.on_user_stream_health(_down(clock, timedelta(seconds=130), attempt=4))

    assert len(published.published) == 1


def test_the_return_of_the_stream_clears_the_condition_once() -> None:
    source, published, clock = _world()
    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))

    source.on_user_stream_health(_connected(clock))
    source.on_user_stream_health(_connected(clock))

    assert published.cleared == [_key()]


def test_a_link_that_drops_again_inside_the_cooldown_sends_no_second_pair() -> None:
    source, published, clock = _world()
    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))
    source.on_user_stream_health(_connected(clock))
    clock.advance(timedelta(minutes=3))

    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))
    source.on_user_stream_health(_connected(clock))

    assert len(published.published) == 1
    assert published.cleared == [_key()]


def test_an_outage_after_the_cooldown_is_a_new_alert() -> None:
    source, published, clock = _world()
    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))
    source.on_user_stream_health(_connected(clock))
    clock.advance(timedelta(minutes=11))

    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))

    assert len(published.published) == 2


def test_a_stream_nobody_wants_any_more_is_not_an_outage() -> None:
    source, published, clock = _world()

    source.on_user_stream_health(
        UserStreamHealthEvent(
            state=UserStreamState.STOPPED,
            since=clock.now() - timedelta(hours=1),
            venue=VENUE,
        )
    )

    assert published.published == []
    assert published.cleared == []


def test_each_venue_has_its_own_outage() -> None:
    source, published, clock = _world()

    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))
    source.on_user_stream_health(
        _down(clock, timedelta(seconds=70), venue=TradingVenue.SPOT_MAINNET)
    )

    assert [alert.subject.venue for alert in published.published] == [
        "futures_mainnet",
        "spot_mainnet",
    ]


def test_the_alert_carries_no_failure_text_from_the_connection() -> None:
    """The supervisor's failure text may name a request; the event has none and the alert copies none."""
    source, published, clock = _world()

    source.on_user_stream_health(_down(clock, timedelta(seconds=70)))

    [alert] = published.published
    assert "listenKey" not in alert.detail
    assert "http" not in alert.detail.lower()
