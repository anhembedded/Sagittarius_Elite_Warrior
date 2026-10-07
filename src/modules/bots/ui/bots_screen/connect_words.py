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
            "system clock."
        ),
        ConnectionFailureKind.KEY_REJECTED: (
            "The exchange rejected the API key. Check the key's IP allowlist "
            "and permissions, or create a new key for this venue."
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
    },
)

#: What a failure's `detail` says when it names the read that failed.
THE_ACCOUNT = "the account"
#: Said after a failure of a bot's venue, whose account Bots → Retry venue
#: account reads again; the Mainnet account window is opened again instead.
RETRY_VENUE_ACCOUNT = "Then choose Bots → Retry venue account."


#: A read that raised instead of answering: its text is behind Details…
#: (`BOT-169`), never in the sentence.
ACCOUNT_UNREADABLE = "The account could not be read."


def failure_cause(problem: ConnectFailure) -> str:
    """What went wrong and what to do about it, without how to read again."""
    sentence = _FAILURES[problem.kind]
    if problem.detail and problem.detail != THE_ACCOUNT:
        return f"{sentence} It stopped while reading {problem.detail}."
    return sentence


def failure_sentence(problem: ConnectFailure) -> str:
    return f"{failure_cause(problem)} {RETRY_VENUE_ACCOUNT}"


def failure_sentence_for_error() -> str:
    return f"{ACCOUNT_UNREADABLE} {RETRY_VENUE_ACCOUNT}"
