"""The exchange connection as the status bar says it (`EPIC-033H`, SPEC-003).

HLD §11.2.2: the connection state is a word in the status bar, never a
colour alone. A failed check also names what to do (`ui-presentation-rule.md`
§10), in one line: the full report — balances, clock skew, position mode —
stays on Tools → Options → Trading, whose Check connection prints it.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
    ExchangeConnectionStatus,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

NOT_CHECKED = "Exchange: not checked"
CHECKING = "Exchange: checking…"

_FAILURES = EnumLabels(
    ConnectionFailureKind,
    {
        ConnectionFailureKind.NOT_CONFIGURED: (
            "no API key. Save one in Tools → Options → Trading."
        ),
        ConnectionFailureKind.BAD_SIGNATURE: (
            "the API secret does not match the key. Copy it again in "
            "Tools → Options → Trading."
        ),
        ConnectionFailureKind.CLOCK_SKEW: (
            "this computer's clock is too far from the exchange's. Resync the "
            "system clock and check again."
        ),
        ConnectionFailureKind.KEY_EXPIRED: (
            "the exchange refused the API key. It may have expired or be a key "
            "for another venue; get a new testnet key."
        ),
        ConnectionFailureKind.NETWORK: (
            "the exchange could not be reached. Check the network or proxy and "
            "check again."
        ),
        ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
            "the account is in Hedge Mode. Switch it to One-way Mode on Binance "
            "and check again."
        ),
    },
)


def connection_word(status: ExchangeConnectionStatus) -> str:
    """The status bar's text after a check."""
    if status.failure is None:
        return f"Exchange: connected ({status.venue.name})"
    if status.reachable:
        return f"Exchange: connected ({status.venue.name}), cannot trade"
    return "Exchange: not connected"


def failure_text(status: ExchangeConnectionStatus) -> str | None:
    """What went wrong and what to do, or `None` when nothing did."""
    if status.failure is None:
        return None
    return f"{status.venue.name}: {_FAILURES[status.failure]}"


def error_text(error: str) -> str:
    """A check that raised instead of answering."""
    return f"The connection check failed: {error}"
