"""`IChannelCatalogBuilder` — the channels this host has *right now* (`EPIC-036D1`).

`IAlertChannelCatalog` is the catalog of the run: built once at boot, fixed for its
life, because the lanes and the hub's routing are fixed with it. A page that saves a
webhook and then sends a test needs the other thing: the catalog as the stores
answer at this moment, built the way boot builds it, and thrown away after use.
Only a test message goes through it; a real alert never does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.alerting.contracts.i_alert_channel_catalog import (
    IAlertChannelCatalog,
)


class IChannelCatalogBuilder(ABC):
    @abstractmethod
    def build(self) -> IAlertChannelCatalog:
        """A new catalog of every declared channel configured on this host now;
        empty when none is. Reads the secret stores; sends nothing."""
