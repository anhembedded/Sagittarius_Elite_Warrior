"""`EPIC-047E` — port: the way a request reaches the VPS host from the Bots tab (Add to VPS).

@details The Bots tab designs and backtests a bot on this computer; Add to VPS sends it to the host as one `add` request
(`HostControlAction.ADD`), which the host answers in its own words after its own gate. The port is the host's control door
(`IHostControl`) seen from the Bots tab: one request in, the host's recorded reply out. It is not `IHostControl` itself
because the application already binds that name to the *local* running host (`bot stop` and the other verbs), and a bot
sent to the VPS must never go to the wrong one. The shell implements it over the VPS link (`shell/vps_tab/`).

Sending connects the link if the VPS tab has not been opened yet: the owner asked for the VPS in that act.

@par Extension cases
  · a second host - another implementation chosen by the profile in use; nothing here names a host;
  · more than one request at once (a whole plan) - the caller loops, as `bot apply` does; the port stays one request.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.core.contracts.host_control import (
    HostControlReply,
    HostControlRequest,
)


class IVpsDelivery(ABC):
    @abstractmethod
    def send(self, request: HostControlRequest, wait_s: float) -> HostControlReply:
        """Carries `request` to the VPS host and waits at most `wait_s` for its recorded reply; never raises for a
        link that is down (the reply says nothing was sent)."""
