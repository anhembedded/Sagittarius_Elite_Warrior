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
from dataclasses import dataclass, replace
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_event_publisher import (
    IEventPublisher,
)
from Sagittarius_Elite_Warrior.src.core.repo_root import DATA_ROOT_ENV
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.wake_signal import (
    WakeSignal,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_outbox import IOutbox
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_recovery_stalled_event import (
    BotRecoveryStalledEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.events.bot_stop_gave_up_event import (
    BotStopGaveUpEvent,
)
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.i_bot_store import IBotStore
from Sagittarius_Elite_Warrior.src.modules.bots.contracts.testing.contract_bot_store import (
    sample_bot,
)
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot import BotLifecycle
from Sagittarius_Elite_Warrior.src.modules.bots.domain.bot_lifecycle_fsm_matrix import (
    BotLifecycleState,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.i_market_data_sources import (
    IMarketDataSources,
)
from Sagittarius_Elite_Warrior.src.modules.market_data.contracts.testing.fake_market_stream import (
    FakeMarketStream,
)
from Sagittarius_Elite_Warrior.src.modules.operations.contracts.i_alert_channels import (
    IAlertChannels,
)
from Sagittarius_Elite_Warrior.src.shell.composition_root import create_app
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.bots_module_world import (
    GRID_CONFIG,
)
from Sagittarius_Elite_Warrior.tests.integration.modules.bots.grid_fake_exchange import (
    FakeStreamSources,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from sagittarius_engine import App
from sagittarius_engine.infrastructure.config.config_manager import ConfigManager

WAIT_S = 15.0
_TOKEN = "Sk3l3t0n-T0ken_xyz"  # noqa: S105 - a made-up token the leak check looks for
WEBHOOK = f"https://discord.com/api/webhooks/998877/{_TOKEN}"
_RATE_LIMITED = WebhookResponse(429, {"Retry-After": "2"}, b'{"retry_after": 2}')


@dataclass
class Skeleton:
    app: App
    transport: FakeWebhookTransport
    clock: FakeAlertClock

    def save(self, state: BotLifecycleState) -> None:
        """Write the sample bot in `state` through the bots' own store."""
        stored = sample_bot()
        definition = replace(stored.bot.definition, config=GRID_CONFIG)
        bot = replace(stored.bot, definition=definition, lifecycle=BotLifecycle(state))
        store = self.app.container.resolve(IBotStore)  # type: ignore[type-abstract]
        store.save(replace(stored, bot=bot, runtime={}))

    def wait_for_posts(self, count: int) -> None:
        while len(self.transport.posts) < count:
            self.transport.posted.clear()
            if len(self.transport.posts) >= count:
                return
            assert self.transport.posted.wait(WAIT_S), f"no POST #{count}"

    def nudge_after(self, wait: timedelta) -> None:
        """Move the alert clock and wake the lanes, as their poll would."""
        self.clock.advance(wait)
        self.app.container.resolve(WakeSignal).notify()


def _boot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    store: InMemorySecretStore,
    transport: FakeWebhookTransport,
) -> Skeleton:
    monkeypatch.setenv(DATA_ROOT_ENV, str(tmp_path))
    clock = FakeAlertClock()
    transport.clock = clock.now
    app = create_app(ConfigManager())
    container = app.container
    container.singleton(ChannelSecrets, ChannelSecrets(store))
    container.singleton(IWebhookTransport, transport)
    container.singleton(IAlertClock, clock)
    real_sources = container.resolve(IMarketDataSources)  # type: ignore[type-abstract]
    container.singleton(
        IMarketDataSources, FakeStreamSources(real_sources, FakeMarketStream())
    )
    app.boot()
    return Skeleton(app, transport, clock)


@pytest.fixture
def skeleton(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Skeleton]:
    booted = _boot(
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

    first, second = skeleton.transport.posts
    content = str(first.body["content"])
    assert "CRITICAL" in content
    assert "Bot halted: grid one" in content
    assert first.url == WEBHOOK
    assert (first.at, second.at) == (start, start + timedelta(seconds=2))
    outbox = skeleton.app.container.resolve(IOutbox)  # type: ignore[type-abstract]
    history = [
        (entry.record.alert.kind.name, [d.state for d in entry.deliveries])
        for entry in outbox.history(10)
    ]
    assert history == [("BOT_HALTED", [DeliveryState.SENT])]
    assert _TOKEN not in caplog.text


def test_an_error_and_a_stop_that_gave_up_each_reach_discord_once(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    booted = _boot(
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

    heads = [
        str(post.body["content"]).splitlines()[0] for post in booted.transport.posts
    ]
    assert "Bot error: grid one" in heads[0]
    assert "Stop failed: grid one" in heads[1]


def test_a_wait_that_stalled_reaches_discord_as_one_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`EPIC-042C`: the module subscribed the stalled event; a wait is silent on entry, so this
    is the owner's only word of a feed that does not return (review of PR #552)."""
    booted = _boot(
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
                bot_id="abc123", reason="price_feed_stale", waited_s=900
            )
        )
        booted.wait_for_posts(1)
    finally:
        booted.app.stop()

    [post] = booted.transport.posts
    content = str(post.body["content"])
    assert "WARNING" in content
    assert "Bot recovery stalled: grid one" in content


def test_the_host_hears_that_a_channel_carries_bot_events(skeleton: Skeleton) -> None:
    alerts = skeleton.app.container.resolve(IAlertChannels)  # type: ignore[type-abstract]

    assert alerts.carries_bot_events()


def test_without_a_webhook_nothing_is_posted_and_the_host_still_warns(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    transport = FakeWebhookTransport()
    booted = _boot(monkeypatch, tmp_path, InMemorySecretStore(), transport)
    alerts = booted.app.container.resolve(IAlertChannels)  # type: ignore[type-abstract]
    try:
        assert not alerts.carries_bot_events()
        booted.save(BotLifecycleState.DRAFT)
        booted.save(BotLifecycleState.HALTED)
    finally:
        booted.app.stop()

    assert transport.posts == []
