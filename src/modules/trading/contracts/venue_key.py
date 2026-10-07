"""`BUG-176` — one venue's key as the Options page lists it, never the secret.

@details The fingerprint is the first four and last four characters of the key
and nothing between: enough to tell two keys apart in a screenshot without the
key being usable from it. A key too short to show eight characters of without
showing most of it is shown masked entirely.
"""

from __future__ import annotations

from dataclasses import dataclass

from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.i_exchange_credentials_provider import (
    CredentialsSource,
)
from Sagittarius_Elite_Warrior.src.support.binance_gateway.contracts.trading_venue import (
    TradingVenue,
)

_SHOWN = 4
_MASK = "••••"
_ELLIPSIS = "…"


def key_fingerprint(api_key: str) -> str:
    if len(api_key) < 4 * _SHOWN:
        return _MASK
    return f"{api_key[:_SHOWN]}{_ELLIPSIS}{api_key[-_SHOWN:]}"


@dataclass(frozen=True)
class VenueKey:
    venue: TradingVenue
    #: `None` when the venue has no key.
    fingerprint: str | None
    source: CredentialsSource
