"""`BUG-262` — what each `ConnectionFailureKind` says, with what to do, in one place.

@details The Bots screen's Connect step (`connect_failure_words.py`) and a refused order session
(`session_block_words.py`) word the same failure of the same account read; one table keeps them
from drifting. It is checked complete at import, so a kind added to `ConnectionFailureKind` fails
here rather than showing a blank.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

CONNECTION_FAILURE_SENTENCES: dict[ConnectionFailureKind, str] = {
    ConnectionFailureKind.NOT_CONFIGURED: (
        "No API key for this venue. Save one in Tools → Options → Trading."
    ),
    ConnectionFailureKind.BAD_SIGNATURE: (
        "The API secret does not match the key. Copy it again in "
        "Tools → Options → Trading."
    ),
    ConnectionFailureKind.CLOCK_SKEW: (
        "This computer's clock is too far from the exchange's. Resync the system clock."
    ),
    ConnectionFailureKind.KEY_REJECTED: (
        "The exchange does not accept this API key. A testnet key does not work "
        "on mainnet, nor the reverse. Check the key's IP allowlist and "
        "permissions, or create a new key for this venue."
    ),
    ConnectionFailureKind.NETWORK: (
        "The exchange could not be reached. Check the network or proxy."
    ),
    ConnectionFailureKind.MAINTENANCE: (
        "The exchange is under maintenance: it answered with a web page, "
        "not with data. Wait a few minutes."
    ),
    ConnectionFailureKind.WITHDRAWAL_ENABLED: (
        "The API key can withdraw funds, so the app refuses it. Create a "
        "read-only key (reading only, withdrawals off) and use that."
    ),
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
        "The account is in Hedge Mode. Switch it to One-way Mode on Binance."
    ),
    ConnectionFailureKind.RATE_LIMITED: (
        "The exchange asked this app to slow down and is not being asked "
        "until its pause ends. Nothing is wrong with the key or the network."
    ),
}

_MISSING = [
    kind.name
    for kind in ConnectionFailureKind
    if not CONNECTION_FAILURE_SENTENCES.get(kind)
]
if _MISSING:
    raise ValueError(f"connection failure kinds without a sentence: {_MISSING}")
