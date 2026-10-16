"""`EPIC-036G` — the Discord channel: it never raises, reads its webhook by name at
each send, and no part of the webhook reaches a log, a reason or the outbox."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
    DiscordWebhookChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.memory_alert_settings import (
    InMemoryAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.alert_hub import (
    AlertHub,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_delivery import (
    ChannelDelivery,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    WebhookResponse,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_alert_clock import (
    FakeAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DeliveryPolicy,
    NoisePolicy,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.delivery_state import (
    DeliveryState,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    CountingWakeup,
    an_alert,
)

_ID = "112233445566778899"
_TOKEN = "Zq9-xY_wEbH00kT0k3n"  # noqa: S105 - a made-up token the leak test looks for
WEBHOOK = f"https://discord.com/api/webhooks/{_ID}/{_TOKEN}"

#: Every piece of the webhook a leak could show: whole, its token, its id.
_SECRET_PARTS = (WEBHOOK, _TOKEN, _ID)

#: Every answer a POST can get, and "no answer".
_EVERY_OUTCOME: tuple[WebhookResponse | WebhookUnreachableError, ...] = (
    WebhookResponse(204),
    WebhookResponse(429, {"Retry-After": "2"}, b'{"retry_after": 2}'),
    WebhookResponse(400, {}, f'{{"message": "bad {WEBHOOK}"}}'.encode()),
    WebhookResponse(401),
    WebhookResponse(404, {}, b'{"message": "Unknown Webhook", "code": 10015}'),
    WebhookResponse(503, {}, f"upstream {WEBHOOK} down".encode()),
    WebhookUnreachableError("timed out"),
)


def _channel(
    transport: FakeWebhookTransport, store: ISecretStore | None = None
) -> DiscordWebhookChannel:
    secrets = (
        store
        if store is not None
        else InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})
    )
    return DiscordWebhookChannel(secrets, transport)


def test_a_halt_is_posted_to_the_stored_webhook_once() -> None:
    transport = FakeWebhookTransport()

    result = _channel(transport).deliver(an_alert(), Loudness.LOUD)

    assert result.ok
    assert [post.url for post in transport.posts] == [WEBHOOK]
    assert "BOT_HALTED title" in str(transport.posts[0].body["content"])


def test_the_webhook_is_read_at_each_send_so_a_rotation_applies_to_the_next() -> None:
    transport = FakeWebhookTransport()
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})
    channel = _channel(transport, store)
    rotated = f"https://discord.com/api/webhooks/{_ID}/rotated"

    channel.deliver(an_alert(), Loudness.LOUD)
    store.write(DISCORD_WEBHOOK_SECRET, rotated)
    channel.deliver(an_alert(), Loudness.LOUD)

    assert [post.url for post in transport.posts] == [WEBHOOK, rotated]


@pytest.mark.parametrize(
    "store",
    [InMemorySecretStore(), UnavailableSecretStore()],
    ids=["nothing stored", "no keyring"],
)
def test_no_stored_webhook_is_refused_without_a_request(store: ISecretStore) -> None:
    transport = FakeWebhookTransport()

    result = _channel(transport, store).deliver(an_alert(), Loudness.LOUD)

    assert result.permanent
    assert transport.posts == []


def test_a_value_that_is_not_a_discord_webhook_is_refused_without_a_request() -> None:
    transport = FakeWebhookTransport()
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: "https://evil.example/x"})

    result = _channel(transport, store).deliver(an_alert(), Loudness.LOUD)

    assert result.permanent
    assert transport.posts == []


def test_a_silent_cell_sets_the_silent_flag() -> None:
    transport = FakeWebhookTransport()

    _channel(transport).deliver(an_alert(), Loudness.SILENT)

    assert transport.posts[0].body["flags"] == 4096


@pytest.mark.parametrize("outcome", _EVERY_OUTCOME)
def test_the_channel_never_raises(
    outcome: WebhookResponse | WebhookUnreachableError,
) -> None:
    result = _channel(FakeWebhookTransport(default=outcome)).deliver(
        an_alert(), Loudness.LOUD
    )

    assert result.ok or result.reason


def test_no_part_of_the_webhook_reaches_a_log_an_error_a_reason_or_the_outbox(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Red-flag test (N3): every answer Discord can give, through the real hub,
    worker pass and outbox, and the captured log, every reason and the stored
    rows hold no piece of the webhook."""
    clock = FakeAlertClock()
    transport = FakeWebhookTransport(script=_EVERY_OUTCOME)
    outbox = SqliteOutbox(tmp_path / "alerts.sqlite3")
    catalog = RegisteredChannelCatalog({"discord": _channel(transport)})
    policy = DeliveryPolicy()
    hub = AlertHub(
        outbox,
        catalog,
        InMemoryAlertSettings(),
        clock,
        CountingWakeup(),
        NoisePolicy(),
        policy,
    )
    delivery = ChannelDelivery(outbox, catalog, clock, hub, policy)
    with caplog.at_level(logging.DEBUG):
        for number in range(len(_EVERY_OUTCOME)):
            hub.publish(an_alert(reason=str(number)))
            delivery.run_due("discord")
            clock.advance(timedelta(minutes=10))
    rows = outbox.history(100)
    stored = b"".join(path.read_bytes() for path in tmp_path.glob("alerts.sqlite3*"))
    outbox.close()
    # Each reason as the channel gave it: a later success overwrites the row.
    direct = [
        _channel(FakeWebhookTransport(default=outcome)).deliver(
            an_alert(), Loudness.LOUD
        )
        for outcome in _EVERY_OUTCOME
    ]
    texts = [record.getMessage() for record in caplog.records]
    texts += [result.reason for result in direct]
    texts += [d.reason for entry in rows for d in entry.deliveries]
    texts += [entry.record.alert.detail for entry in rows]

    assert transport.script == []  # every answer was given at least once
    for part in _SECRET_PARTS:
        assert not [text for text in texts if part in text], part
        assert part.encode() not in stored, part


def test_a_429_is_never_retried_before_discords_wait(tmp_path: Path) -> None:
    """The real worker pass and outbox: Discord asks for 2 s, nothing is sent at
    1 s, the retry goes at 2 s and is SENT."""
    clock = FakeAlertClock()
    transport = FakeWebhookTransport(
        script=[WebhookResponse(429, {}, b'{"retry_after": 2}')],
        clock=clock.now,
    )
    outbox = SqliteOutbox(tmp_path / "alerts.sqlite3")
    catalog = RegisteredChannelCatalog({"discord": _channel(transport)})
    policy = DeliveryPolicy()
    hub = AlertHub(
        outbox,
        catalog,
        InMemoryAlertSettings(),
        clock,
        CountingWakeup(),
        NoisePolicy(),
        policy,
    )
    delivery = ChannelDelivery(outbox, catalog, clock, hub, policy)
    start = clock.now()
    hub.publish(an_alert())

    delivery.run_due("discord")
    clock.advance(timedelta(seconds=1))
    delivery.run_due("discord")
    assert len(transport.posts) == 1

    clock.advance(timedelta(seconds=1))
    delivery.run_due("discord")

    assert [post.at for post in transport.posts] == [
        start,
        start + timedelta(seconds=2),
    ]
    states = [d.state for d in outbox.history(1)[0].deliveries]
    outbox.close()
    assert states == [DeliveryState.SENT]
