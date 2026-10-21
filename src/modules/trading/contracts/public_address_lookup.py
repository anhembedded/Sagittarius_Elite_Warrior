"""What asking an outside server for this machine's public address came back with (`BOT-224`).

A key's IP whitelist is matched against the address the exchange sees, which is
the machine's public address and never its LAN address. The lookup is either an
address or the reason there is none, so a caller reads one outcome and never a
`None` that could mean either.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class PublicAddressFailure(Enum):
    #: No address service answered in time (no network, a proxy, a firewall).
    UNREACHABLE = "unreachable"
    #: A service answered, but not with a public IPv4 address.
    UNREADABLE = "unreadable"


@dataclass(frozen=True)
class PublicAddressLookup:
    """Exactly one of `address` and `failure` is set."""

    address: str | None = None
    failure: PublicAddressFailure | None = None

    def __post_init__(self) -> None:
        if (self.address is None) == (self.failure is None):
            raise ValueError("a lookup holds either an address or a failure")

    @classmethod
    def found(cls, address: str) -> PublicAddressLookup:
        return cls(address=address)

    @classmethod
    def failed(cls, failure: PublicAddressFailure) -> PublicAddressLookup:
        return cls(failure=failure)
