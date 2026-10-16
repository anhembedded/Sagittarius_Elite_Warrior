"""`EPIC-036G` — the Discord channel is in the catalog exactly when a Discord
webhook is stored on this host, and the decision never logs the secret."""

from __future__ import annotations

import logging

import pytest
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_WEBHOOK_SECRET,
    DiscordWebhookChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.memory_alert_settings import (
    InMemoryAlertSettings,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.application.channel_alerting_status import (
    ChannelAlertingStatus,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.composition.channel_bindings import (
    ChannelSecrets,
    build_channel_catalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.testing.fake_webhook_transport import (
    FakeWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_settings import (
    AlertSettings,
)
from Sagittarius_Elite_Warrior.tests.secret_stores import (
    InMemorySecretStore,
    UnavailableSecretStore,
)

WEBHOOK = "https://discord.com/api/webhooks/42/t0ken-value"


class _Resolver:
    """The two ports a channel factory asks for."""

    def __init__(self, store: ISecretStore) -> None:
        self._ports: dict[type, object] = {
            ChannelSecrets: ChannelSecrets(store),
            IWebhookTransport: FakeWebhookTransport(),
        }

    def resolve[T](self, abstract: type[T]) -> T:
        return self._ports[abstract]  # type: ignore[return-value]


def test_a_stored_webhook_puts_discord_in_the_catalog(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK})

    with caplog.at_level(logging.INFO, logger="App.Alerting"):
        catalog = build_channel_catalog(_Resolver(store))

    assert catalog.channel_ids() == ("discord",)
    assert isinstance(catalog.channel("discord"), DiscordWebhookChannel)
    assert "discord is on" in caplog.text
    assert "t0ken-value" not in caplog.text


@pytest.mark.parametrize(
    "store",
    [InMemorySecretStore(), UnavailableSecretStore()],
    ids=["nothing stored", "no keyring"],
)
def test_no_webhook_leaves_the_catalog_empty_and_says_why(
    store: ISecretStore, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="App.Alerting"):
        catalog = build_channel_catalog(_Resolver(store))

    assert catalog.channel_ids() == ()
    assert "discord is off: no webhook is stored" in caplog.text


def test_a_value_that_is_not_a_discord_webhook_turns_the_channel_off_without_quoting_it(
    caplog: pytest.LogCaptureFixture,
) -> None:
    store = InMemorySecretStore(
        **{DISCORD_WEBHOOK_SECRET: "https://evil.example/s3cret"}
    )

    with caplog.at_level(logging.INFO, logger="App.Alerting"):
        catalog = build_channel_catalog(_Resolver(store))

    assert catalog.channel_ids() == ()
    assert "not a Discord webhook URL" in caplog.text
    assert "s3cret" not in caplog.text


def test_the_host_says_a_channel_carries_bot_events_only_with_a_webhook() -> None:
    with_webhook = build_channel_catalog(
        _Resolver(InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}))
    )
    without = build_channel_catalog(_Resolver(InMemorySecretStore()))

    assert ChannelAlertingStatus(
        with_webhook, InMemoryAlertSettings()
    ).carries_bot_events()
    assert not ChannelAlertingStatus(
        without, InMemoryAlertSettings()
    ).carries_bot_events()


def test_a_disabled_channel_carries_nothing() -> None:
    catalog = build_channel_catalog(
        _Resolver(InMemorySecretStore(**{DISCORD_WEBHOOK_SECRET: WEBHOOK}))
    )
    settings = InMemoryAlertSettings(
        AlertSettings(disabled_channels=frozenset({"discord"}))
    )

    assert not ChannelAlertingStatus(catalog, settings).carries_bot_events()
