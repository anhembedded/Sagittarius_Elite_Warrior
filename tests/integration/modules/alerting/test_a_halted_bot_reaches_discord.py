"""`EPIC-036G` — the walking skeleton, end to end on the graph `create_app()` builds.

A bot written HALTED through the bots' own store reaches one Discord webhook as
one CRITICAL alert: the bot store's `BotChangedEvent`, the alert source the
module subscribed, the hub, the SQLite outbox, the Discord lane, the real
`DiscordWebhookChannel` and the webhook read by name from a secret store. Only
the network is fake — Discord's (`IWebhookTransport`) and the market stream the
bots' price watch opens for a halted bot — with the secret store and the alert
clock, each rebound on the container before the boot, as the bots' fake-exchange
journeys do. Discord first answers 429 with a 2 s wait; nothing is posted before
it, and the retry is SENT. No part of the webhook is in the log.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_kind import AlertKind
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_auto_recovered_event import (
    BotAutoRecoveredEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_risk_changed_event import (
    BotRiskChangedEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.risk_state import RiskLevel
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.events.user_stream_health_event import (
    UserStreamHealthEvent,
    UserStreamState,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)
from Sagittarius_Elite_Warrior.tests.discord_posts import (
    is_heartbeat,
    wait_until_the_heartbeat_is_told,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.alerting.skeleton_world import (
    TOKEN,
    WEBHOOK,
    Skeleton,
    boot_skeleton,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore

_RATE_LIMITED = WebhookResponse(429, {"Retry-After": "2"}, b'{"retry_after": 2}')


@pytest.fixture
def skeleton(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Skeleton]:
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(script=[_RATE_LIMITED]),
    )
    try:
        yield booted
    finally:
        booted.app.stop()


def test_a_halted_bot_reaches_discord_once_after_its_retry_after(
    skeleton: Skeleton, caplog: pytest.LogCaptureFixture
) -> None:
    start = skeleton.clock.now()
    with caplog.at_level(logging.DEBUG):
        skeleton.save(BotLifecycleState.DRAFT)
        skeleton.save(BotLifecycleState.HALTED)
        skeleton.wait_for_posts(1)

        skeleton.nudge_after(timedelta(seconds=2))
        skeleton.wait_for_posts(2)

    first, second = skeleton.posts
    content = str(first.body["content"])
    assert "CRITICAL" in content
    assert "Bot halted: grid one" in content
    assert first.url == WEBHOOK
    assert (first.at, second.at) == (start, start + timedelta(seconds=2))
    outbox = skeleton.app.container.resolve(IOutbox)  # type: ignore[type-abstract]
    history = [
        (entry.record.alert.kind.name, [d.state for d in entry.deliveries])
        for entry in outbox.history(10)
        if entry.record.alert.kind is not AlertKind.HEARTBEAT
    ]
    assert history == [("BOT_HALTED", [DeliveryState.SENT])]
    assert TOKEN not in caplog.text


def test_an_error_and_a_stop_that_gave_up_each_reach_discord_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.ERROR)
        booted.wait_for_posts(1)
        events.publish(BotStopGaveUpEvent(bot_id="abc123", retries=5))
        booted.wait_for_posts(2)
    finally:
        booted.app.stop()

    heads = [str(post.body["content"]).splitlines()[0] for post in booted.posts]
    assert "Bot error: grid one" in heads[0]
    assert "Stop failed: grid one" in heads[1]


def test_a_wait_that_stalled_reaches_discord_as_one_alert(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-042C`: the module subscribed the stalled event; a wait is silent on entry, so this
    is the owner's only word of a recovery that does not come (review of PR #552). A reason that
    has no kind of its own is the generic `BOT_RECOVERY_STALLED` warning."""
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.AWAITING_RECOVERY)
        events.publish(
            BotRecoveryStalledEvent(
                bot_id="abc123", reason="user_stream_down", waited_s=900
            )
        )
        booted.wait_for_posts(1)
    finally:
        booted.app.stop()

    [post] = booted.posts
    content = str(post.body["content"])
    assert "WARNING" in content
    assert "Bot recovery stalled: grid one" in content


def test_an_automatic_recovery_reaches_discord_as_one_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-042D`: the module subscribed the recovered event, so the owner on a headless host
    hears of each recovery with the budget it leaves."""
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.RUNNING)
        events.publish(BotAutoRecoveredEvent("abc123", "price_feed_stale", 1, 3))
        booted.wait_for_posts(1)
    finally:
        booted.app.stop()

    [post] = booted.posts
    content = str(post.body["content"])
    assert "WARNING" in content
    assert "Bot recovered by itself: grid one" in content
    assert "attempt 1 of 3" in content


def test_a_liquidation_warning_reaches_discord_as_one_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-036B1`: the module subscribed the risk event; the owner's VPS bot tells its approach."""
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.RUNNING)
        events.publish(
            BotRiskChangedEvent(
                bot_id="abc123",
                symbol="ETHUSDT",
                level=RiskLevel.WARN,
                reason="The mark price 1900 is 9.50% from the exchange's liquidation price 1720",
                distance=Decimal("0.095"),
                mark_price=Decimal(1900),
                liquidation_price=Decimal(1720),
            )
        )
        booted.wait_for_posts(1)
    finally:
        booted.app.stop()

    [post] = booted.posts
    content = str(post.body["content"])
    assert "WARNING" in content
    assert "Liquidation risk: grid one" in content
    assert "liquidation price 1720" in content


def test_a_user_stream_outage_reaches_discord_as_one_alert_about_the_venue(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-036B1`: the module subscribed trading's stream health; one message, not one per bot."""
    booted = boot_skeleton(
        monkeypatch,
        tmp_path,
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}),
        FakeWebhookTransport(),
    )
    events = booted.app.container.resolve(IEventPublisher)  # type: ignore[type-abstract]
    try:
        events.publish(
            UserStreamHealthEvent(
                state=UserStreamState.RECONNECTING,
                since=booted.clock.now() - timedelta(seconds=90),
                attempt=4,
                venue=TradingVenue.FUTURES_MAINNET,
            )
        )
        booted.wait_for_posts(1)
    finally:
        booted.app.stop()

    [post] = booted.posts
    content = str(post.body["content"])
    assert "CRITICAL" in content
    assert "Account stream down: Futures Mainnet" in content


def test_the_apps_own_heartbeat_is_not_one_of_the_posts_a_journey_counts(
    skeleton: Skeleton,
) -> None:
    """`BUG-252`: every journey here boots the app, whose housekeeping thread sends a heartbeat a
    second in; a run that lasts that long found two posts where it expects one. The wait makes
    it certain, and the journey must still see only its own alert."""
    wait_until_the_heartbeat_is_told(skeleton.transport, skeleton.clock)
    skeleton.save(BotLifecycleState.DRAFT)
    skeleton.save(BotLifecycleState.ERROR)
    skeleton.wait_for_posts(1)

    [post] = skeleton.posts

    assert "Bot error: grid one" in str(post.body["content"])
    assert any(is_heartbeat(p) for p in skeleton.transport.posts), (
        "no heartbeat was told"
    )


def test_the_host_hears_that_a_channel_carries_bot_events(skeleton: Skeleton) -> None:
    alerts = skeleton.app.container.resolve(IAlertChannels)  # type: ignore[type-abstract]

    assert alerts.carries_bot_events()


def test_without_a_webhook_nothing_is_posted_and_the_host_still_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transport = FakeWebhookTransport()
    booted = boot_skeleton(monkeypatch, tmp_path, InMemorySecretStore(), transport)
    alerts = booted.app.container.resolve(IAlertChannels)  # type: ignore[type-abstract]
    try:
        assert not alerts.carries_bot_events()
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.HALTED)
    finally:
        booted.app.stop()

    assert transport.posts == []
