"""`EPIC-047E` — port: what the VPS tab's host last published (`HostWorld`).

@details The remote backend of the Bots screen (`adapters/remote_host/`) answers the screen's
queries from this and nothing else, so it can be tested against a dictionary and run over any
transport. The link to the host implements it (`shell/vps_link/`); the module never learns
whether the picture came over SSH, a socket or a test.

@par Extension cases
  · a second host at once (not offered, `EPIC-047` G2) — one more `IHostWorld`, the tab picks by
    profile; nothing here names a host.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.bots.contracts.host_world import HostWorld


class IHostWorld(ABC):
    @abstractmethod
    def current(self) -> HostWorld:
        """The picture now. Never blocks and never reaches a network: a disconnected link returns
        the last picture with `connected` false."""
