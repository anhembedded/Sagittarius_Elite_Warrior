"""`EPIC-034D`, `EPIC-034H` — what a failed read of a venue's account says, in the
user's words.

One sentence per failure kind, each naming what to do (`ui-presentation-rule.md`
§10); the table is checked complete at import, so a kind added to
`ConnectionFailureKind` fails at import here rather than showing a blank (the
application layer may not import `support/ui_kit`'s `EnumLabels`, which does
the same for the screens). The
sentence is told **once**, in the message bar (`BUG-181`, `ui-presentation-rule.md`
§10); every other surface — the identity strip, the chart's place, the Plan's
Connect item, Start's reason — carries the short state below, never the advice.
It does not say how to read again: the bar's Retry does, a refusal has nothing to
retry.
"""

from __future__ import annotations

from Sagittarius_Elite_Warrior.src.modules.trading.contracts.connect_failure import (
    ConnectFailure,
)
from Sagittarius_Elite_Warrior.src.modules.trading.contracts.exchange_connection_status import (
    ConnectionFailureKind,
)

_FAILURES: dict[ConnectionFailureKind, str] = {
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
}

#: What each kind is in a few words, for the surfaces that are not the bar.
_STATES: dict[ConnectionFailureKind, str] = {
    ConnectionFailureKind.NOT_CONFIGURED: "no API key",
    ConnectionFailureKind.BAD_SIGNATURE: "secret does not match the key",
    ConnectionFailureKind.CLOCK_SKEW: "clock out of sync",
    ConnectionFailureKind.KEY_REJECTED: "key refused",
    ConnectionFailureKind.NETWORK: "exchange unreachable",
    ConnectionFailureKind.MAINTENANCE: "exchange under maintenance",
    ConnectionFailureKind.WITHDRAWAL_ENABLED: "key can withdraw",
    ConnectionFailureKind.HEDGE_MODE_UNSUPPORTED: "Hedge Mode is on",
}

_MISSING = [
    kind.name
    for kind in ConnectionFailureKind
    if not _FAILURES.get(kind) or not _STATES.get(kind)
]
if _MISSING:
    raise ValueError(f"connection failure kinds without a sentence: {_MISSING}")

NOT_CONNECTED = "Not connected"

#: What a failure's `detail` says when it names the read that failed.
THE_ACCOUNT = "the account"


def failure_cause(failure: ConnectFailure) -> str:
    """What went wrong and what to do about it, without how to read again."""
    sentence = _FAILURES[failure.kind]
    if failure.reply:
        sentence = f"{sentence} The exchange said: {failure.reply}"
    if failure.detail and failure.detail != THE_ACCOUNT:
        return f"{sentence} It stopped while reading {failure.detail}."
    return sentence


def state_words(failure: ConnectFailure) -> str:
    """What a failed read is, in a few words: "key refused"."""
    return _STATES[failure.kind]


def failure_state(failure: ConnectFailure) -> str:
    """The short state a surface that is not the message bar shows:
    "Not connected: key refused" (`BUG-181`)."""
    return f"{NOT_CONNECTED}: {state_words(failure)}"


#: A read that raised instead of answering: its text is behind Details…
#: (`BOT-169`), never in the sentence.
ACCOUNT_UNREADABLE = "The account could not be read."
#: The same, in a few words.
ACCOUNT_UNREADABLE_STATE = "the account could not be read"
