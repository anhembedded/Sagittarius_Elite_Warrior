"""The port that asks the outside world for this machine's public IPv4 address (`BOT-224`).

Binance names no address of its own (`outbound_address_check.py`), so the only
way to learn the address a key's IP whitelist must hold is to ask an IP-echo
service. That is a call to a third party, so it is made only when the user asks
for it (Options > Trading > Show public IP), never at startup or in the
background.

Plausible extensions, each a local change: another echo service (one more entry
in the adapter's source list); an IPv6 lookup (a second method here and a second
button label).
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressLookup,
)


class IPublicAddressReader(ABC):
    @abstractmethod
    def read(self) -> PublicAddressLookup:
        """Blocks for at most a few seconds; a failure is a lookup, never an exception."""
        raise NotImplementedError("read")
