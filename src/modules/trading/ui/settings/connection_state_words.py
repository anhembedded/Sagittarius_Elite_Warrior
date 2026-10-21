"""`BUG-176` — one row's connection state of the Trading page, in plain words.

@details A sentence per `ConnectionFailureKind`, each saying what to do, in an
`EnumLabels` so a new kind without words fails on import. The page's text no
longer says which environment a key is for: the page lists venues and the venue
is the row's, so the words only say what Binance answered. `-2015` is worded for
every cause the exchange does not tell apart (another environment's key, an IP off
the key's allowlist, a missing permission): a LAN address such as 192.168.x.x never
matches an allowlist, only the public address does.
"""

from __future__ import annotations

from enum import Enum, auto

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

CONNECTED = "Connected"
NOT_CHECKED = "Not checked yet. Use Check connections."
NO_KEY = "No key. Use Add key…"


class StateKind(Enum):
    """What a venue row's state says, decided where the check is read; the view draws its look
    from it and never from the words."""

    UNKNOWN = auto()  # no key, or not checked yet
    CONNECTED = auto()
    ERROR = auto()


_NOT_UNDERSTOOD = "Binance answered, but not in a way this page can read."

_FAILURES = EnumLabels(
    ConnectionFailureKind,
    {
        ConnectionFailureKind.NOT_CONFIGURED: NO_KEY,
        ConnectionFailureKind.BAD_SIGNATURE: (
            "The secret does not match the key. Replace the key and enter the "
            "secret again, with no extra or missing characters."
        ),
        ConnectionFailureKind.CLOCK_SKEW: (
            "This computer's clock is too far from Binance's. Resync the system "
            "clock and check again."
        ),
        ConnectionFailureKind.KEY_REJECTED: (
            "Binance refused the key. It may belong to another environment, its "
            "IP allowlist may not include this computer's public address (a LAN "
            "address such as 192.168.x.x never matches), or it may lack a "
            "permission. Fix it on Binance or replace the key."
        ),
        ConnectionFailureKind.NETWORK: (
            "Could not reach Binance. Check the network or proxy and check again."
        ),
        ConnectionFailureKind.MAINTENANCE: (
            "Binance is unavailable (maintenance or a gateway error). Try again later."
        ),
        ConnectionFailureKind.WITHDRAWAL_ENABLED: (
            "The key can withdraw funds, so the app refuses it. Replace it with a "
            "key that has withdrawals turned off."
        ),
        ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
            "The account is in Hedge Mode. Switch it to One-way Mode on Binance, "
            "then check again."
        ),
        ConnectionFailureKind.RATE_LIMITED: (
            "Binance asked this app to slow down; no request is sent until its "
            "pause ends. The key and the network are fine. Check again in a minute."
        ),
    },
)


def failure_words(kind: ConnectionFailureKind) -> str:
    """What Binance's answer means and what to do, for one failure kind."""
    return _FAILURES[kind]


def state_of(status: ExchangeConnectionStatus) -> tuple[str, StateKind]:
    """The row text for one connection check, and what kind of state it is."""
    if status.failure is not None:
        return failure_words(status.failure), StateKind.ERROR
    if not status.reachable:
        return _NOT_UNDERSTOOD, StateKind.ERROR
    return CONNECTED, StateKind.CONNECTED
