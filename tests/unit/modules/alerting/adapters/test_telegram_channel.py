"""`EPIC-036C1` - the Telegram channel: it never raises, reads its token and chat by name at
each send, and no part of the token reaches a log, a reason or the outbox."""

from __future__ import annotations

import logging
from datetime import timedelta
from pathlib import Path

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.memory_alert_settings import (
    InMemoryAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.sqlite_outbox import (
    SqliteOutbox,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
    TelegramChannel,
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
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import (
    CountingWakeup,
    an_alert,
)

_ID = "987654321"
_KEY = "Zq9-xY_wEbH00kT0k3nZq9xYwEbH00kT0k3n"
TOKEN = f"{_ID}:{_KEY}"
CHAT = "5550123"
SEND_URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
_SECRET_PARTS = (TOKEN, _KEY, f"bot{TOKEN}")

_EVERY_OUTCOME: tuple[WebhookResponse | WebhookUnreachableError, ...] = (
    WebhookResponse(200, {}, b'{"ok": true}'),
    WebhookResponse(429, {}, b'{"ok": false, "parameters": {"retry_after": 2}}'),
    WebhookResponse(
        400, {}, f'{{"description": "Bad Request: chat not found {TOKEN}"}}'.encode()
    ),
    WebhookResponse(401, {}, f"bad {TOKEN}".encode()),
    WebhookResponse(
        403, {}, b'{"description": "Forbidden: bot was blocked by the user"}'
    ),
    WebhookResponse(502, {}, f"upstream {SEND_URL} down".encode()),
    WebhookUnreachableError("timed out"),
)


def _channel(
    transport: FakeWebhookTransport, store: ISecretStore | None = None
) -> TelegramChannel:
    secrets = (
        store
        if store is not None
        else InMemorySecretStore(
            **{TELEGRAM_TOKEN_SECRET: TOKEN, TELEGRAM_CHAT_SECRET: CHAT}
        )
    )
    return TelegramChannel(secrets, transport)


def test_a_halt_is_posted_to_the_bot_api_for_the_stored_chat_once() -> None:
    transport = FakeWebhookTransport(default=WebhookResponse(200))

    result = _channel(transport).deliver(an_alert(), Loudness.LOUD)

    assert result.ok
    assert [post.url for post in transport.posts] == [SEND_URL]
    assert transport.posts[0].body["chat_id"] == CHAT
    assert "BOT_HALTED title" in str(transport.posts[0].body["text"])


def test_the_token_is_read_at_each_send_so_a_rotation_applies_to_the_next() -> None:
    transport = FakeWebhookTransport(default=WebhookResponse(200))
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: TOKEN, TELEGRAM_CHAT_SECRET: CHAT}
    )
    channel = _channel(transport, store)
    rotated = f"{_ID}:rotated-key-0123456789"

    channel.deliver(an_alert(), Loudness.LOUD)
    store.write(TELEGRAM_TOKEN_SECRET, rotated)
    channel.deliver(an_alert(), Loudness.LOUD)

    assert [post.url for post in transport.posts] == [
        SEND_URL,
        f"https://api.telegram.org/bot{rotated}/sendMessage",
    ]


@pytest.mark.parametrize(
    "store",
    [
        InMemorySecretStore(),
        UnavailableSecretStore(),
        InMemorySecretStore(**{TELEGRAM_TOKEN_SECRET: TOKEN}),
        InMemorySecretStore(**{TELEGRAM_CHAT_SECRET: CHAT}),
    ],
    ids=["nothing", "no keyring", "no chat", "no token"],
)
def test_a_missing_token_or_chat_is_refused_without_a_request(
    store: ISecretStore,
) -> None:
    transport = FakeWebhookTransport()

    result = _channel(transport, store).deliver(an_alert(), Loudness.LOUD)

    assert result.permanent
    assert transport.posts == []


@pytest.mark.parametrize(
    ("token", "chat"),
    [
        ("not a token", CHAT),
        (TOKEN, "not a chat"),
        (f"{TOKEN}/../x", CHAT),
        (TOKEN, "42/evil"),
    ],
    ids=["token", "chat", "token path", "chat path"],
)
def test_a_value_of_the_wrong_shape_is_refused_without_a_request(
    token: str, chat: str
) -> None:
    """The token goes into a URL path: only the shape Telegram issues may be put there."""
    transport = FakeWebhookTransport()
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: token, TELEGRAM_CHAT_SECRET: chat}
    )

    result = _channel(transport, store).deliver(an_alert(), Loudness.LOUD)

    assert result.permanent
    assert transport.posts == []


def test_a_channel_username_is_a_usable_chat() -> None:
    transport = FakeWebhookTransport(default=WebhookResponse(200))
    store = InMemorySecretStore(
        **{TELEGRAM_TOKEN_SECRET: TOKEN, TELEGRAM_CHAT_SECRET: "@owner_alerts"}
    )

    assert _channel(transport, store).deliver(an_alert(), Loudness.LOUD).ok
    assert transport.posts[0].body["chat_id"] == "@owner_alerts"


@pytest.mark.parametrize("outcome", _EVERY_OUTCOME)
def test_the_channel_never_raises(
    outcome: WebhookResponse | WebhookUnreachableError,
) -> None:
    result = _channel(FakeWebhookTransport(default=outcome)).deliver(
        an_alert(), Loudness.LOUD
    )

    assert result.ok or result.reason


def test_no_part_of_the_token_reaches_a_log_an_error_a_reason_or_the_outbox(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Red-flag test (N3): every answer Telegram can give, through the real hub, worker pass
    and outbox; the captured log, every reason and the stored rows hold no piece of the token."""
    clock = FakeAlertClock()
    transport = FakeWebhookTransport(script=_EVERY_OUTCOME)
    outbox = SqliteOutbox(tmp_path / "alerts.sqlite3")
    catalog = RegisteredChannelCatalog({"telegram": _channel(transport)})
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
            delivery.run_due("telegram")
            clock.advance(timedelta(minutes=10))
    rows = outbox.history(100)
    stored = b"".join(path.read_bytes() for path in tmp_path.glob("alerts.sqlite3*"))
    outbox.close()
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

    assert transport.script == []
    for part in _SECRET_PARTS:
        assert not [text for text in texts if part in text], part
        assert part.encode() not in stored, part
