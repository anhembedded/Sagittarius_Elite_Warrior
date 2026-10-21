"""`BOT-224` — the Options page's public IP read-out, in plain words.

@details A key's IP whitelist on Binance is matched against the public address
the exchange sees, which the app cannot read from Binance. The page asks an
IP-echo service when the user presses Show public IP and says what to do with
the answer; a failure is one sentence in an `EnumLabels`, so a new failure kind
without words fails on import.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.public_address_lookup import (
    PublicAddressFailure,
    PublicAddressLookup,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

BUSY = "Looking up this machine's public IP…"
CAPTION = "Public IP:"
ADVICE = (
    "Put this address in the key's IP whitelist on Binance. A LAN address "
    "such as 192.168.x.x never matches: Binance only sees the public one."
)

_FAILURES = EnumLabels(
    PublicAddressFailure,
    {
        PublicAddressFailure.UNREACHABLE: (
            "Could not look up the public IP: no IP service answered. "
            "Check the network or proxy and try again."
        ),
        PublicAddressFailure.UNREADABLE: (
            "Could not look up the public IP: the service did not answer with "
            "a public IPv4 address. Try again later."
        ),
    },
)


def failure_words(failure: PublicAddressFailure) -> str:
    return _FAILURES[failure]


def read_out_of(lookup: PublicAddressLookup) -> tuple[str, str]:
    """The address, and the sentence for the page: `(address, "")` when found,
    `("", reason)` when not."""
    if lookup.failure is not None:
        return "", failure_words(lookup.failure)
    return lookup.address or "", ""
