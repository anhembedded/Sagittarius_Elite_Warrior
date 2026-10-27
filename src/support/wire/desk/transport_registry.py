"""`EPIC-047D` — which transport a profile's protocol means: the one place a protocol is mapped to a class.

A profile names a `LinkProtocol`; the registry builds a new `ILinkTransport` for each connection
attempt. A second protocol is one `register` call at the composition root and one new adapter (P7).
A factory that cannot be built (the SSH library is not installed in this build) is
`TransportMissingError`, a sentence the profile's owner reads, not an `ImportError` on a worker thread.
"""

from __future__ import annotations

from collections.abc import Callable

from Sagittarius_Elite_Warrior.src.core.contracts.link_profile import (
    LinkProtocol,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.i_link_transport import (
    ILinkTransport,
)
from Sagittarius_Elite_Warrior.src.support.wire.desk.contracts.link_errors import (
    TransportMissingError,
)


class TransportRegistry:
    def __init__(self) -> None:
        self._factories: dict[LinkProtocol, Callable[[], ILinkTransport]] = {}

    def register(
        self, protocol: LinkProtocol, factory: Callable[[], ILinkTransport]
    ) -> None:
        self._factories[protocol] = factory

    def protocols(self) -> tuple[LinkProtocol, ...]:
        return tuple(self._factories)

    def create(self, protocol: LinkProtocol) -> ILinkTransport:
        """A fresh transport.

        @raise TransportMissingError no factory, or one that cannot import its library."""
        factory = self._factories.get(protocol)
        if factory is None:
            raise TransportMissingError(protocol.value)
        try:
            return factory()
        except ImportError as failure:
            raise TransportMissingError(protocol.value) from failure
