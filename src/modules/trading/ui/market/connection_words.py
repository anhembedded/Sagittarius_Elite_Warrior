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
from Sagittarius_Elite_Warrior.src.support.ui_kit.meaning_colours import Tone
from Sagittarius_Elite_Warrior.src.support.ui_kit.state_look import StateLook

NOT_CHECKED = "Exchange: not checked"
CHECKING = "Exchange: checking…"
NOT_CONNECTED = "Exchange: not connected"

#: The icon and tone beside the word (`EPIC-043C`); a connection not checked yet has none.
CHECKING_LOOK = StateLook("clock", Tone.NEUTRAL)
NOT_CONNECTED_LOOK = StateLook("circle-x", Tone.NEGATIVE)
#: A word and its look, for `MarketView.set_connection_text(*state)`.
CHECKING_STATE: tuple[str, StateLook] = (CHECKING, CHECKING_LOOK)
NOT_CONNECTED_STATE: tuple[str, StateLook] = (NOT_CONNECTED, NOT_CONNECTED_LOOK)
#: A check that raised instead of answering; the exception is the notice's detail.
CHECK_FAILED = "The connection check failed. Check the network and try again."

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
        ConnectionFailureKind.KEY_REJECTED: (
            "the exchange does not accept this API key. A testnet key does not "
            "work on mainnet, nor the reverse. Otherwise check the key's IP "
            "allowlist and permissions, or get a new key for this venue."
        ),
        ConnectionFailureKind.NETWORK: (
            "the exchange could not be reached. Check the network or proxy and "
            "check again."
        ),
        ConnectionFailureKind.MAINTENANCE: (
            "the exchange is unavailable (maintenance or a gateway error). Try "
            "again later."
        ),
        ConnectionFailureKind.WITHDRAWAL_ENABLED: (
            "the API key can withdraw funds. The app refuses it: create a "
            "read-only key (reading only, withdrawals off) and use that."
        ),
        ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
            "the account is in Hedge Mode. Switch it to One-way Mode on Binance "
            "and check again."
        ),
        ConnectionFailureKind.RATE_LIMITED: (
            "the exchange asked this app to slow down; no request is sent until "
            "its pause ends. The key and the network are fine. Check again in a "
            "minute."
        ),
    },
)


def connection_word(status: ExchangeConnectionStatus) -> str:
    """The status bar's text after a check."""
    if status.failure is None:
        return f"Exchange: connected ({status.venue.name})"
    if status.reachable:
        return f"Exchange: connected ({status.venue.name}), cannot trade"
    return NOT_CONNECTED


def connection_look(status: ExchangeConnectionStatus) -> StateLook:
    """The icon and tone beside `connection_word(status)`: connected, reachable but not allowed to
    trade (a warning), or not connected."""
    if status.failure is None:
        return StateLook("circle-check-big", Tone.POSITIVE)
    if status.reachable:
        return StateLook("triangle-alert", Tone.CAUTION)
    return NOT_CONNECTED_LOOK


def failure_text(status: ExchangeConnectionStatus) -> str | None:
    """What went wrong and what to do, or `None` when nothing did."""
    if status.failure is None:
        return None
    return f"{status.venue.name}: {_FAILURES[status.failure]}"
