"""Which channels this application has: the one list a channel is added to.

A channel is one adapter file and one descriptor appended to `CHANNEL_DESCRIPTORS`
(`EPIC-036C` adds Discord and Telegram here). The hub, the worker, the outbox and
the module are not touched: that is the seam `test_a_second_channel_needs_no_application_change`
locks.

The factory runs when the alerting graph is first built, with the finished
container behind a `PortResolver`, so a channel can ask for `ISecretStore` or the
configuration without `register()` resolving anything.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.core.contracts.i_operations_registry import (
    PortResolver,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.adapters.registered_channel_catalog import (
    RegisteredChannelCatalog,
)
from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel import (
    IAlertChannel,
)

type AlertChannelFactory = Callable[[PortResolver], IAlertChannel]


@dataclass(frozen=True, slots=True)
class AlertChannelDescriptor:
    """One channel this application offers, under the id the settings name it by."""

    channel_id: str
    factory: AlertChannelFactory


#: Empty in `EPIC-036A`: the core ships no real channel.
CHANNEL_DESCRIPTORS: tuple[AlertChannelDescriptor, ...] = ()


def build_channel_catalog(resolver: PortResolver) -> RegisteredChannelCatalog:
    """The catalog of every declared channel, built now.

    @raise ValueError Two descriptors share an id.
    """
    channels: dict[str, IAlertChannel] = {}
    for descriptor in CHANNEL_DESCRIPTORS:
        if descriptor.channel_id in channels:
            raise ValueError(
                f"Alert channel {descriptor.channel_id!r} is declared twice"
            )
        channels[descriptor.channel_id] = descriptor.factory(resolver)
    return RegisteredChannelCatalog(channels)
