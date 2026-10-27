"""`EPIC-047D` — the transports this build offers for a connection profile's protocol.

SSH is the only one (`AsyncSshTransport`, on `asyncssh`). It is named by import path (`Deferred`), so a
run that never opens the VPS link imports no SSH library at boot, and a build without the library
answers `TransportMissingError`, a sentence the person reads, instead of failing on import. A Unix
socket, a VPN or a TLS endpoint is one more `register` line and one adapter (P7).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.core.contracts.deferred import Deferred
from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import LinkProtocol
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.i_link_transport import (
    ILinkTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)

SSH_TRANSPORT: Deferred[ILinkTransport] = Deferred(
    "Sagittarius_Elite_Warrior.src.support.wire.desk.asyncssh_transport:AsyncSshTransport"
)


def build_transport_registry() -> TransportRegistry:
    registry = TransportRegistry()
    registry.register(LinkProtocol.SSH, SSH_TRANSPORT)
    return registry
