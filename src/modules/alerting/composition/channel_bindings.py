"""Which channels this application has: the one list a channel is added to.

A channel is one adapter file and one descriptor appended to `CHANNEL_DESCRIPTORS`
(`EPIC-036G` added Discord; `EPIC-036C` adds Telegram here). The hub, the worker,
the outbox and the module are not touched: that is the seam
`test_a_second_channel_needs_no_application_change` locks.

The factory runs when the alerting graph is first built, with the finished
container behind a `PortResolver`, so a channel can ask for its secret store or
its transport without `register()` resolving anything. **A factory answers
`None` when its channel is not configured on this host** (no secret stored):
the channel is then not in the catalog, no lane is started for it, and the
host's "does a channel carry bot events?" (`IAlertingStatus`) says no. The
decision is logged either way, never with the secret.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PortResolver,
)
from Sagittarius_Elite_Warrior.src.core.contracts.i_secret_store import ISecretStore
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_message import (
    is_discord_webhook_url,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.discord_webhook_channel import (
    DISCORD_CHANNEL_ID,
    DISCORD_WEBHOOK_SECRET,
    DiscordWebhookChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.paced_channel import (
    PacedChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_clock import (
    IAlertClock,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_channel_catalog_builder import (
    IChannelCatalogBuilder,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_webhook_transport import (
    IWebhookTransport,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.domain.alert_policies import (
    DISCORD_PACING,
)

logger = logging.getLogger("App.Alerting")

type AlertChannelFactory = Callable[[PortResolver], IAlertChannel | None]


@dataclass(frozen=True, slots=True)
class AlertChannelDescriptor:
    """One channel this application offers, under the id the settings name it by."""

    channel_id: str
    factory: AlertChannelFactory


@dataclass(frozen=True, slots=True)
class ChannelSecrets:
    """The store the channels read their secrets from, by name (N3; decision D3:
    systemd credential, then a permission-checked file, then the keyring)."""

    store: ISecretStore


def discord_channel(resolver: PortResolver) -> IAlertChannel | None:
    """The Discord channel, when a Discord webhook is stored on this host."""
    secrets = resolver.resolve(ChannelSecrets).store
    webhook = (secrets.read(DISCORD_WEBHOOK_SECRET) or "").strip()
    # The credential is named in the text, never passed to the logger: no value
    # derived from the secret store reaches a log call (CodeQL
    # py/clear-text-logging-sensitive-data).
    if not webhook:
        logger.info(
            "[alert-channel] discord is off: no webhook is stored in the Discord "
            "webhook credential (alerting_discord_webhook)"
        )
        return None
    if not is_discord_webhook_url(webhook):
        logger.warning(
            "[alert-channel] discord is off: the Discord webhook credential "
            "(alerting_discord_webhook) does not hold a Discord webhook URL"
        )
        return None
    logger.info(
        "[alert-channel] discord is on: webhook read from the Discord webhook "
        "credential (alerting_discord_webhook)"
    )
    return PacedChannel(
        DiscordWebhookChannel(secrets, resolver.resolve(IWebhookTransport)),  # type: ignore[type-abstract]
        resolver.resolve(IAlertClock),  # type: ignore[type-abstract]
        DISCORD_PACING,
    )


CHANNEL_DESCRIPTORS: tuple[AlertChannelDescriptor, ...] = (
    AlertChannelDescriptor(DISCORD_CHANNEL_ID, discord_channel),
)


def build_channel_catalog(resolver: PortResolver) -> RegisteredChannelCatalog:
    """The catalog of every declared channel configured on this host, built now.

    @raise ValueError Two descriptors share an id.
    """
    channels: dict[str, IAlertChannel] = {}
    declared: set[str] = set()
    for descriptor in CHANNEL_DESCRIPTORS:
        if descriptor.channel_id in declared:
            raise ValueError(
                f"Alert channel {descriptor.channel_id!r} is declared twice"
            )
        declared.add(descriptor.channel_id)
        channel = descriptor.factory(resolver)
        if channel is not None:
            channels[descriptor.channel_id] = channel
    return RegisteredChannelCatalog(channels)


class DescriptorChannelCatalogBuilder(IChannelCatalogBuilder):
    """`IChannelCatalogBuilder` over `CHANNEL_DESCRIPTORS`: the boot's own function,
    run again (`EPIC-036D1`)."""

    def __init__(self, resolver: PortResolver) -> None:
        self._resolver = resolver

    def build(self) -> IAlertChannelCatalog:
        return build_channel_catalog(self._resolver)
