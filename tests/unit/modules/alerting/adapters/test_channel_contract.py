"""`EPIC-036C1` - one contract every webhook channel keeps, run over each of them.

A channel never raises, turns "no answer" into a failure that may pass, turns a rate limit into
a wait the worker honours, and turns a refusal into one that will not (research 036 §1). The
rows are the channels: a third is one row.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta

import pytest
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
    DiscordWebhookChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.telegram_channel import (
    TELEGRAM_CHAT_SECRET,
    TELEGRAM_TOKEN_SECRET,
    TelegramChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
    WebhookResponse,
    WebhookUnreachableError,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.loudness import Loudness
from Sagittarius_Elite_Warrior.tests.secret_stores import InMemorySecretStore
from Sagittarius_Elite_Warrior.tests.unit.modules.alerting.world import an_alert

type ChannelOf = Callable[[IWebhookTransport], IAlertChannel]

_DISCORD = "https://discord.com/api/webhooks/112233445566778899/Zq9-xY_wEbH00kT0k3n"
_TELEGRAM_TOKEN = "987654321:Zq9-xY_wEbH00kT0k3nZq9xYwEbH00kT0k3n"  # noqa: S105 - made up

CHANNELS: dict[str, ChannelOf] = {
    "discord": lambda transport: DiscordWebhookChannel(
        InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: _DISCORD}), transport
    ),
    "telegram": lambda transport: TelegramChannel(
        InMemorySecretStore(
            **{TELEGRAM_TOKEN_SECRET: _TELEGRAM_TOKEN, TELEGRAM_CHAT_SECRET: "5550123"}
        ),
        transport,
    ),
}

#: How each platform says "wait": Discord in the body's top level, Telegram under `parameters`.
_RATE_LIMITED = {
    "discord": WebhookResponse(429, {}, b'{"retry_after": 3}'),
    "telegram": WebhookResponse(429, {}, b'{"parameters": {"retry_after": 3}}'),
}
_ACCEPTED = {"discord": WebhookResponse(204), "telegram": WebhookResponse(200)}


def _deliver(name: str, outcome: WebhookResponse | WebhookUnreachableError):
    channel = CHANNELS[name](FakeWebhookTransport(default=outcome))
    return channel.deliver(an_alert(), Loudness.LOUD)


@pytest.mark.parametrize("name", CHANNELS)
def test_an_accepted_message_is_sent(name: str) -> None:
    assert _deliver(name, _ACCEPTED[name]).ok


@pytest.mark.parametrize("name", CHANNELS)
def test_no_answer_is_a_failure_that_may_pass_and_never_raises(name: str) -> None:
    result = _deliver(name, WebhookUnreachableError("timed out"))

    assert not result.ok
    assert not result.permanent
    assert result.retry_after is None


@pytest.mark.parametrize("name", CHANNELS)
def test_a_rate_limit_is_a_wait_the_worker_honours(name: str) -> None:
    result = _deliver(name, _RATE_LIMITED[name])

    assert result.retry_after == timedelta(seconds=3)
    assert not result.permanent


@pytest.mark.parametrize("name", CHANNELS)
@pytest.mark.parametrize("status", [401, 403, 404])
def test_a_refusal_will_not_be_retried(name: str, status: int) -> None:
    result = _deliver(name, WebhookResponse(status, {}, b"{}"))

    assert result.permanent
    assert result.retry_after is None


@pytest.mark.parametrize("name", CHANNELS)
def test_a_server_error_is_retried(name: str) -> None:
    result = _deliver(name, WebhookResponse(503, {}, b""))

    assert not result.ok
    assert not result.permanent
