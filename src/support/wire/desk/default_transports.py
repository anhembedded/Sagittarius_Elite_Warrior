"""`EPIC-047D` — the transports this build offers for a connection profile's protocol.

SSH is the only protocol a profile can name today, and its adapter (`AsyncSshTransport`, on
`asyncssh`) arrives with the dependency the owner approves (`EPIC-047D`, "Dependency"). Until it does
the registry holds no transport and `TransportRegistry.create(LinkProtocol.SSH)` answers
`TransportMissingError`, a sentence the person reads, instead of failing on import. When it lands it is
one line here, `registry.register(LinkProtocol.SSH, Deferred("…asyncssh_transport:AsyncSshTransport"))`,
named by import path so a run that never opens the VPS link imports no SSH library at boot. A Unix
socket, a VPN or a TLS endpoint is one more line and one adapter (P7).
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.support.wire.desk.transport_registry import (
    TransportRegistry,
)


def build_transport_registry() -> TransportRegistry:
    return TransportRegistry()
