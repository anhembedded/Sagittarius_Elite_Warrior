"""`EPIC-034D` — what the Connect step says, in the user's words.

One sentence per failure kind, each naming what to do (`ui-presentation-rule.md`
§10); `EnumLabels` refuses to build when a kind has none, so a kind added to
`ConnectionFailureKind` fails at import here rather than showing a blank. The
Trading screen words the same kinds for its status bar
(`modules/trading/ui/market/connection_words.py`); a module may not import
another's `ui/`, and this sentence says what a bot's owner does next, so the
two are written apart.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)
from Sagittarius_Elite_Warrior.src.support.ui_kit.enum_labels import EnumLabels

CONNECTING = "Reading the account…"
NOT_CONNECTED = "No bot selected."
CONNECTED = "Connected"
NOT_CONNECTED_STATUS = "Not connected"
CONNECTING_STATUS = "Connecting…"

_FAILURES = EnumLabels(
    ConnectionFailureKind,
    {
        ConnectionFailureKind.NOT_CONFIGURED: (
            "No API key for this venue. Save one in Tools → Options → Trading."
        ),
        ConnectionFailureKind.BAD_SIGNATURE: (
            "The API secret does not match the key. Copy it again in "
            "Tools → Options → Trading."
        ),
        ConnectionFailureKind.CLOCK_SKEW: (
            "This computer's clock is too far from the exchange's. Resync the "
            "system clock, then choose Bots → Retry venue account."
        ),
        ConnectionFailureKind.KEY_REJECTED: (
            "The exchange rejected the API key. Check the key's IP allowlist "
            "and permissions, or create a new key for this venue."
        ),
        ConnectionFailureKind.NETWORK: (
            "The exchange could not be reached. Check the network or proxy, then choose Bots → Retry venue account."
        ),
        ConnectionFailureKind.MAINTENANCE: (
            "The exchange is under maintenance: it answered with a web page, "
            "not with data. Wait a few minutes, then choose Bots → Retry venue account."
        ),
        ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: (
            "The account is in Hedge Mode. Switch it to One-way Mode on "
            "Binance, then choose Bots → Retry venue account."
        ),
    },
)

#: What a failure's `detail` says when it names the read that failed.
_THE_ACCOUNT = "the account"


def failure_sentence(failure: ConnectFailure) -> str:
    sentence = _FAILURES[failure.kind]
    if failure.detail and failure.detail != _THE_ACCOUNT:
        return f"{sentence} It stopped while reading {failure.detail}."
    return sentence


def failure_sentence_for_error(error: str) -> str:
    """A read that raised instead of answering."""
    return f"The account could not be read: {error}. Choose Bots → Retry venue account."
